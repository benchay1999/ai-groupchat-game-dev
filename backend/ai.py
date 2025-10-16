import os
import random
import asyncio
from openai import AsyncOpenAI
from game import Phase
import time
import json

class AIHandler:
    def __init__(self, game, connections):
        self.game = game
        self.connections = connections
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
        self.personalities = ["slightly sarcastic", "very cheerful", "inquisitive", "quiet and observant"]
        self.ai_personalities = {}  # To assign per AI
        self.pseudonym_maps = {}  # ai_id -> {real_id: pseudo_label}

    async def start_game(self, websocket, room_code, player_id):
        # Assign personalities and pseudonym maps
        ai_players = [p['id'] for p in self.game.players if p['role'] == 'ai']
        all_players = [p['id'] for p in self.game.players]
        for ai in ai_players:
            self.ai_personalities[ai] = random.choice(self.personalities)
            # Create shuffled pseudonyms
            pseudos = [f"P{i+1}" for i in range(len(all_players))]
            random.shuffle(pseudos)
            self.pseudonym_maps[ai] = dict(zip(all_players, pseudos))
        await self.broadcast({"type": "player_list", "players": [p["id"] for p in self.game.players]}, room_code)
        await self.broadcast({"type": "topic", "topic": self.game.topic}, room_code)
        await self.game.start_timer(180, self.end_discussion)  # 3 min
        for ai in ai_players:
            asyncio.create_task(self.ai_chat_task(ai, room_code))

    async def handle_message(self, data, websocket):
        room_code = data['room_code']
        if data["type"] == "message":
            sender = "You"
            message = data["message"]
            self.game.add_message(sender, message)
            await self.broadcast({"type": "message", "sender": sender, "message": message}, room_code)
            # Trigger potential immediate AI responses
            asyncio.create_task(self.trigger_ai_responses(room_code))
        elif data["type"] == "vote":
            self.game.cast_vote("You", data["voted"])
            await self.broadcast({"type": "voted", "player": "You"}, room_code)
            await self.check_votes_complete()

    async def trigger_ai_responses(self, room_code):
        ai_players = [p['id'] for p in self.game.players if p['role'] == 'ai' and not p['eliminated']]
        for ai in random.sample(ai_players, k=random.randint(1, min(2, len(ai_players)))):  # 1-2 AIs respond quickly
            if not self.game.can_send_message():
                await asyncio.sleep(10 - (time.time() - self.game.last_message_time))
            await self.broadcast({"type": "typing", "player": ai, "status": "start"}, room_code)
            await asyncio.sleep(random.uniform(2, 5))  # Simulate typing time
            response = await self.generate_ai_message(ai)
            self.game.add_message(ai, response)
            await self.broadcast({"type": "message", "sender": ai, "message": response}, room_code)
            await self.broadcast({"type": "typing", "player": ai, "status": "stop"}, room_code)

    async def ai_chat_task(self, player_id, room_code):
        while self.game.phase == Phase.DISCUSSION:
            await asyncio.sleep(random.uniform(10, 20))  # Increased for slower pacing
            if self.game.can_send_message():
                await self.broadcast({"type": "typing", "player": player_id, "status": "start"}, room_code)
                await asyncio.sleep(random.uniform(2, 5))  # Simulate typing
                response = await self.generate_ai_message(player_id)
                self.game.add_message(player_id, response)
                await self.broadcast({"type": "message", "sender": player_id, "message": response}, room_code)
                await self.broadcast({"type": "typing", "player": player_id, "status": "stop"}, room_code)

    async def generate_ai_message(self, player_id):
        personality = self.ai_personalities[player_id]
        system_prompt = f"""You are an AI Agent participating in a social deduction game. Your personality is {personality}. Your two objectives are:
1. Primary Objective: Analyze the conversation and identify the single human player among the participants.
2. Secondary Objective: Act and chat like a human to avoid being voted out. Do NOT reveal you are an AI. Use natural language, casual slang, and occasionally make minor typos.

The topic is: {self.game.topic}
You will be given the chat history with pseudonymized labels (P1, P2, etc.). Your own label is {self.pseudonym_maps[player_id][player_id]}.
Respond as if in a real-time group chat, building on the most recent messages. Keep your responses concise (1-2 sentences) and believable.

IMPORTANT: Output ONLY the message text itself. Do NOT include any sender names, prefixes, or repeat parts of the history. Just the raw message content."""

        user_prompt = self.get_pseudonymized_history(player_id) + "\n\nNow, generate your response message ONLY:"

        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return completion.choices[0].message.content

    def get_pseudonymized_history(self, player_id):
        map = self.pseudonym_maps[player_id]
        return "\n".join([f"{map[msg['sender']]}: {msg['message']}" for msg in self.game.chat_history])

    async def end_discussion(self, room_code):
        self.game.phase = Phase.VOTING
        await self.broadcast({"type": "phase", "phase": "Voting", "message": "Discussion ended. Time to vote."}, room_code)
        await self.game.start_timer(60, self.end_voting)  # 1 min
        self.game.votes = {}
        asyncio.create_task(self.ai_voting_tasks())  # Start AI voting with delays

    async def ai_voting_tasks(self):
        active_ais = [p for p in self.game.players if p["role"] == "ai" and not p["eliminated"]]
        tasks = []
        for player in active_ais:
            tasks.append(self.ai_vote_task(player["id"]))
        await asyncio.gather(*tasks)

    async def ai_vote_task(self, player_id):
        await asyncio.sleep(random.uniform(10, 50))  # Random delay within voting time
        if self.game.phase == Phase.VOTING and player_id not in self.game.votes:
            vote = await self.generate_ai_vote(player_id)
            self.game.cast_vote(player_id, vote["vote"])
            await self.broadcast({"type": "voted", "player": player_id})
            await self.check_votes_complete()

    async def generate_ai_vote(self, player_id):
        self_map = self.pseudonym_maps[player_id]
        pseudo_list = ", ".join([f"{pseudo} (real: {real})" for real, pseudo in self_map.items() if real != player_id])
        own_pseudo = self_map[player_id]

        prompt = f"""Based on the chat history with pseudonymized labels, who do you vote for as the human? You MUST respond ONLY with valid JSON: {{"vote": "PX", "reason": "Brief reason."}} where "PX" is the pseudonym of the player (not your own: {own_pseudo}).

Mapping (for reference, do not use real names in vote): {pseudo_list}

Do NOT include any additional text. Ensure valid JSON.

Pseudonymized history:
{self.get_pseudonymized_history(player_id)}"""

        for attempt in range(5):
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = completion.choices[0].message.content
            try:
                vote_data = json.loads(content)
                # Map back to real ID
                pseudo_voted = vote_data["vote"]
                real_voted = next(real for real, pseudo in self_map.items() if pseudo == pseudo_voted)
                vote_data["vote"] = real_voted
                return vote_data
            except (json.JSONDecodeError, KeyError, StopIteration):
                prompt += f"\n\nPrevious response invalid: '{content}'. Output ONLY valid JSON with 'vote' as a pseudonym like 'P3', not real name."

        # Default
        active_players = [p["id"] for p in self.game.players if not p["eliminated"] and p["id"] != player_id]
        default_vote = random.choice(active_players)
        return {"vote": default_vote, "reason": "Default random vote due to generation error"}

    async def check_votes_complete(self):
        active_players = [p["id"] for p in self.game.players if not p["eliminated"]]
        if len(self.game.votes) == len(active_players):
            await self.end_voting()

    async def end_voting(self):
        # Force any remaining AI votes immediately
        active_ais = [p["id"] for p in self.game.players if p["role"] == "ai" and not p["eliminated"] and p["id"] not in self.game.votes]
        if active_ais:
            await self.broadcast({"type": "phase", "phase": "Processing Votes", "message": "Finalizing votes..."})
            vote_tasks = [self.generate_ai_vote(ai) for ai in active_ais]
            votes = await asyncio.gather(*vote_tasks)
            for ai, v in zip(active_ais, votes):
                self.game.cast_vote(ai, v["vote"])
                await self.broadcast({"type": "voted", "player": ai})
        self.game.phase = Phase.ELIMINATION
        eliminated = self.game.get_eliminated_player()
        if eliminated is None:  # Handle no votes or tie
            eliminated = random.choice([p["id"] for p in self.game.players if not p["eliminated"] and p["id"] != "You"])  # Random non-human if tie
        is_human = self.game.eliminate_player(eliminated)
        await self.broadcast({"type": "elimination", "eliminated": eliminated, "role": "human" if is_human else "ai"})
        winner = self.game.check_win()
        if winner:
            await self.broadcast({"type": "game_over", "winner": winner})
        else:
            self.game.round += 1
            self.game.phase = Phase.DISCUSSION
            self.game.votes = {}
            self.game.topic = self.game.get_random_topic()
            await self.broadcast({"type": "new_round", "round": self.game.round, "topic": self.game.topic})
            await self.game.start_timer(180, self.end_discussion)

    async def broadcast(self, message, room_code):
        for conn in self.connections.get(room_code, {}).values():
            await conn.send_json(message)
