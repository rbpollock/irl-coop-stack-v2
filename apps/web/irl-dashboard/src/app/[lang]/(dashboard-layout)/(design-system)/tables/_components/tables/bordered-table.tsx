import { invoicesData } from "../../_data/invoices"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function BorderedTable() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bordered Table</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px] border-r">Invoice</TableHead>
              <TableHead className="border-r">Status</TableHead>
              <TableHead className="border-r">Method</TableHead>
              <TableHead className="text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoicesData.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell className="font-medium border-r">
                  {invoice.id}
                </TableCell>
                <TableCell className="border-r">{invoice.status}</TableCell>
                <TableCell className="border-r">{invoice.method}</TableCell>
                <TableCell className="text-right">{invoice.amount}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
