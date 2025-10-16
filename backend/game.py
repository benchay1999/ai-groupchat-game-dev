import random
from enum import Enum
import asyncio
import time

class Phase(Enum):
    DISCUSSION = "Discussion"
    VOTING = "Voting"
    ELIMINATION = "Elimination"

class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        ai_names = [f"Player {i}" for i in range(1,5)]
        random.shuffle(ai_names)
        self.players = [{"id": "You", "role": "human", "eliminated": False}] + [{"id": name, "role": "ai", "eliminated": False} for name in ai_names]
        self.round = 1
        self.phase = Phase.DISCUSSION
        self.chat_history = []
        self.votes = {}
        self.timer = None
        self.topic = self.get_random_topic()
        self.last_message_time = time.time()  # For cooldown

    def get_random_topic(self):
        topics = [
            "What's the best topping for pizza?",
            "Describe your ideal vacation.",
            "If you could have any superpower, what would it be?",
            "What's your favorite movie and why?",
            "Tell a funny story from your childhood."
        ]
        return random.choice(topics)

    async def start_timer(self, duration, callback):
        self.timer = asyncio.create_task(self._timer(duration, callback))

    async def _timer(self, duration, callback):
        await asyncio.sleep(duration)
        await callback()

    def add_message(self, sender, message):
        self.chat_history.append({"sender": sender, "message": message})
        self.last_message_time = time.time()

    def get_chat_history_str(self):
        return "\n".join([f"{msg['sender']}: {msg['message']}" for msg in self.chat_history])

    def cast_vote(self, voter, voted):
        self.votes[voter] = voted

    def get_eliminated_player(self):
        from collections import Counter
        vote_count = Counter(self.votes.values())
        if not vote_count:
            return None
        max_votes = max(vote_count.values())
        candidates = [player for player, count in vote_count.items() if count == max_votes]
        return random.choice(candidates) if len(candidates) > 1 else candidates[0]

    def eliminate_player(self, player_id):
        for p in self.players:
            if p["id"] == player_id:
                p["eliminated"] = True
                return p["role"] == "human"

    def check_win(self):
        eliminated_ais = sum(1 for p in self.players if p["role"] == "ai" and p["eliminated"])
        if eliminated_ais >= 3:
            return "human"
        if any(p["role"] == "human" and p["eliminated"] for p in self.players):
            return "ai"
        return None

    def can_send_message(self):
        return time.time() - self.last_message_time >= 10
