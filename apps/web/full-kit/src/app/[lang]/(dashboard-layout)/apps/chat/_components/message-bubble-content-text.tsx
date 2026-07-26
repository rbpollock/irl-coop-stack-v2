export function MessageBubbleContentText({ text }: { text: string }) {
  if (!text) return null // Return null if the text is empty

  const urlRegex = /(https?:\/\/[^\s]+)/g // Regex to match URLs
  const parts = text.split(urlRegex) // Split the text into parts using the URL regex

  // Map over each part to render it as either plain text or an anchor tag
  return parts.map((part, index) => {
    // If the part matches the URL regex, render it as an anchor tag
    if (urlRegex.test(part)) {
      return (
        <a
          key={`${part}-${index}`}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 underline-offset-4 hover:underline"
        >
          {part}
        </a>
      )
    }

    // If the part does not match the URL regex, return it as plain text
    return (
      <p key={`${part}-${index}`} className="p-2">
        {part}
      </p>
    )
  })
}
