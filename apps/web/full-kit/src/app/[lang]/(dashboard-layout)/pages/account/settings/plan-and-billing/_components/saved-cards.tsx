import { savedCardsData } from "../../../_data/saved-cards"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { SavedCardsList } from "./saved-cards-list"

export function SavedCards() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved Cards</CardTitle>
        <CardDescription>
          View and manage your stored payment cards for easy checkout.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <SavedCardsList savedCards={savedCardsData} />
      </CardContent>
    </Card>
  )
}
