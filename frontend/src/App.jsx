import { useEffect, useState } from 'react'
import PlayerList from './components/PlayerList'
import ChatWindow from './components/ChatWindow'

function App() {
  const [ws, setWs] = useState(null)
  const [gameState, setGameState] = useState({
    phase: 'Discussion',
    round: 1,
    topic: '',
    chat: [],
    players: [
      { id: 'You', voted: false },
      { id: 'Player 1', voted: false },
      { id: 'Player 2', voted: false },
      { id: 'Player 3', voted: false },
      { id: 'Player 4', voted: false },
    ],
    timer: 180,
  })
  const [typing, setTyping] = useState([])  // Array of players currently typing
  // Add state for room_code
  const [roomCode, setRoomCode] = useState('default-room')  // Or generate/randomize

  useEffect(() => {
    const websocket = new WebSocket(`ws://${process.env.REACT_APP_BACKEND_URL || 'localhost:8000'}/ws/${roomCode}/You`)
    websocket.onopen = () => console.log('Connected')
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      // Update gameState based on data.type
      if (data.type === 'message') {
        setGameState(prev => ({ ...prev, chat: [...prev.chat, { sender: data.sender, message: data.message }] }))
      } else if (data.type === 'typing') {
        setTyping(prev => {
          if (data.status === 'start') {
            return [...new Set([...prev, data.player])]
          } else {
            return prev.filter(p => p !== data.player)
          }
        })
      } else if (data.type === 'phase') {
        setGameState(prev => ({ 
          ...prev, 
          phase: data.phase,
          players: prev.players.map(p => ({ ...p, voted: false })) // Reset voted on new phase
        }))
        // Reset timer based on phase
        if (data.phase === 'Discussion') {
          setGameState(prev => ({ ...prev, timer: 180 }))
        } else if (data.phase === 'Voting') {
          setGameState(prev => ({ ...prev, timer: 60 }))
        } else if (data.phase === 'Processing Votes' || data.phase === 'Elimination') {
          setGameState(prev => ({ ...prev, timer: 0 }))
        }
      } else if (data.type === 'topic') {
        setGameState(prev => ({ ...prev, topic: data.topic }))
      } else if (data.type === 'player_list') {
        setGameState(prev => ({ ...prev, players: data.players.map(id => ({ id, voted: false, eliminated: false })) }))
      } else if (data.type === 'voted') {
        setGameState(prev => ({
          ...prev,
          players: prev.players.map(p => p.id === data.player ? { ...p, voted: true } : p)
        }))
      } else if (data.type === 'elimination') {
        setGameState(prev => ({
          ...prev,
          players: prev.players.map(p => p.id === data.eliminated ? { ...p, eliminated: true } : p)
        }))
        alert(`${data.eliminated} was eliminated and was a ${data.role}`)
      } else if (data.type === 'game_over') {
        alert(`${data.winner.toUpperCase()} wins!`)
      } else if (data.type === 'new_round') {
        setGameState(prev => ({ ...prev, round: data.round, topic: data.topic, phase: 'Discussion', timer: 180 }))
      }
      // Add more handlers
    }
    setWs(websocket)
    return () => websocket.close()
  }, [])

  const sendMessage = (message) => {
    if (ws && gameState.phase === 'Discussion') {
      ws.send(JSON.stringify({ type: 'message', message }))
    }
  }

  const castVote = (voted) => {
    if (ws && gameState.phase === 'Voting' && !gameState.players.find(p => p.id === 'You').voted) {
      ws.send(JSON.stringify({ type: 'vote', voted }))
    }
  }

  // Timer logic
  useEffect(() => {
    const interval = setInterval(() => {
      setGameState(prev => {
        if (prev.timer > 0 && (prev.phase === 'Discussion' || prev.phase === 'Voting')) {
          return { ...prev, timer: prev.timer - 1 }
        }
        return prev
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex h-screen">
      <PlayerList players={gameState.players} phase={gameState.phase} castVote={castVote} />
      <div className="flex-1 flex flex-col">
        <header className="p-4 bg-gray-200">
          Round {gameState.round} - {gameState.phase} - Time: {gameState.timer}s
          <p>Topic: {gameState.topic}</p>
        </header>
        <ChatWindow chat={gameState.chat} typing={typing} />
        <input
          type="text"
          className="p-2 border-t"
          placeholder="Type your message..."
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              sendMessage(e.target.value)
              e.target.value = ''
            }
          }}
          disabled={gameState.phase !== 'Discussion'}
        />
      </div>
    </div>
  )
}

export default App
