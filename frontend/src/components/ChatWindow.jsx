const ChatWindow = ({ chat, typing }) => {
  return (
    <div className="flex-1 p-4 overflow-y-auto">
      {chat.map((msg, idx) => (
        <p key={idx}><strong>{msg.sender}:</strong> {msg.message}</p>
      ))}
      {typing.length > 0 && (
        <p className="text-gray-500 italic">
          {typing.join(', ')} {typing.length > 1 ? 'are' : 'is'} typing...
        </p>
      )}
    </div>
  )
}

export default ChatWindow
