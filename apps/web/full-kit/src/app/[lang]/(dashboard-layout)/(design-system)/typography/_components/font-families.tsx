import { fontFamiliesData } from "../_data/font-families"

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

export function FontFamilies() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Font Families</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Tailwind Classes</TableHead>
              <TableHead>Language</TableHead>
              <TableHead>Example</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {fontFamiliesData.map((font) => (
              <TableRow key={font.name}>
                <TableCell>{font.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{font.class}</Badge>
                </TableCell>
                <TableCell>{font.language}</TableCell>
                <TableCell className={font.class}>{font.example}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
