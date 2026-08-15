import { logsData } from "../../../_data/logs"

import { formatDateWithTime } from "@/lib/utils"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function RecentLogsTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>User Agent</TableHead>
          <TableHead>Device</TableHead>
          <TableHead>Location</TableHead>
          <TableHead>Date</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logsData.map((log) => (
          <TableRow key={log.id}>
            <TableCell>{log.userAgent}</TableCell>
            <TableCell>{log.device}</TableCell>
            <TableCell>{log.location}</TableCell>
            <TableCell>{formatDateWithTime(log.createdAt)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
