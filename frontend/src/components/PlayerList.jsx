const PlayerList = ({ players, phase, castVote }) => {
  return (
    <div className="w-1/4 p-4 bg-gray-100">
      <h2>Players</h2>
      <ul>
        {players.map(player => (
          <li
            key={player.id}
            className={`flex justify-between items-center py-1 ${player.eliminated ? 'text-gray-500' : ''}`}
          >
            {player.id} {player.voted ? '(Voted)' : ''} {player.eliminated ? '(Eliminated)' : ''}
            {phase === 'Voting' && !player.eliminated && player.id !== 'You' && !player.voted && (
              <button
                onClick={() => castVote(player.id)}
                className="ml-2 px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
              >
                Vote to Eliminate
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default PlayerList
