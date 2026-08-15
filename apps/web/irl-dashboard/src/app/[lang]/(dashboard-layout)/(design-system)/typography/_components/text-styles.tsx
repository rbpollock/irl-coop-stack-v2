import { textStylesData } from "../_data/text-styles"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function TextStyles() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Text Styles</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Tailwind Classes</TableHead>
              <TableHead>Usage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {textStylesData.map((text) => (
              <TableRow key={text.name}>
                <TableCell className={text.class}>{text.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{text.class}</Badge>
                </TableCell>
                <TableCell>{text.usage}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
