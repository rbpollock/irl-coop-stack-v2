import { sourcesAndCreditsData } from "../_data/sources-and-credits"

import { Card } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function SourcesAndCreditsTable() {
  return (
    <Card>
      <Table className="!my-0">
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="w-full">URL</TableHead>
            <TableHead>License</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sourcesAndCreditsData.map((datum) => (
            <TableRow key={datum.name}>
              <TableCell>{datum.name}</TableCell>
              <TableCell className="break-all">
                <a href={datum.url} target="_blank" rel="noopener noreferrer">
                  {datum.url}
                </a>
              </TableCell>
              <TableCell>{datum.license}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  )
}
