"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

export function BasicScrollArea() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Scroll-Area</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <ScrollArea className="h-64 w-full rounded-md border p-4">
          In the quiet kingdom of Merrymirth, where laughter was scarce and the
          king’s scowl was a permanent feature, a mysterious figure began to
          stir up chaos. Known only as Jokester, this mischievous prankster had
          a knack for slipping into the castle under the cover of darkness. Each
          night, Jokester would leave jokes in the most peculiar places: riddles
          scribbled on the queen&apos;s tiara, limericks tucked into the folds
          of the royal napkins, and tiny scrolls of puns stuffed into the court
          jester&apos;s oversized shoes. The king, who prided himself on his
          serious demeanor, was livid. He doubled the guards, set traps around
          the castle, and even enlisted the court wizard to cast spells of
          protection. But Jokester was clever, always one step ahead. The pranks
          became bolder: a giant rubber chicken was discovered in the throne
          room; the royal banners were replaced with silly poems about the
          king’s snoring; even the royal toilet paper bore cheeky messages, such
          as, &quotFor throne emergencies only.&quot As the days passed, the
          people of Merrymirth began to notice something strange. While the king
          fumed and plotted, the citizens found the jokes irresistible. Chuckles
          turned into guffaws, and soon the streets were filled with laughter.
          The butcher laughed as he chopped meat, the baker chuckled over his
          loaves, and even the grumpy blacksmith cracked a grin as he hammered.
          The mood of the entire kingdom began to shift. At first, the king
          dismissed it as a nuisance. But when his advisors started laughing
          during royal meetings and the guards failed to keep a straight face on
          duty, he realized that Jokester’s antics were no ordinary mischief.
          What truly infuriated the king was the discovery that the laughter was
          contagious. One night, after finding yet another joke under his
          pillow—this one involving a pun about knights and “armor-gettin’ ready
          for bed”—the king accidentally chuckled. It was a small chuckle,
          barely audible, but it grew. His cheeks twitched, and soon, he erupted
          into uncontrollable laughter. The queen, startled, joined in, and
          within moments, the entire castle echoed with mirth. Jokester,
          watching from a hidden nook, smiled and whispered, “Mission
          accomplished.” From that day on, the kingdom of Merrymirth embraced
          its new identity. Laughter was no longer a rarity; it was a way of
          life. Jokester became a celebrated figure, though no one ever
          discovered their true identity. And as for the king? He still
          pretended to scowl in public, but everyone knew that under his stern
          exterior, a smile was always waiting to escape.
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
