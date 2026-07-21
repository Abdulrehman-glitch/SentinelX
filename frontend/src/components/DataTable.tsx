import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { useUserSettingsQuery } from "../hooks/useUserSettingsQuery";
import { loadStoredUiSettings } from "../utils/accessibility";

type DataTableProps<TData> = {
  title: string;
  description: string;
  data: TData[];
  columns: ColumnDef<TData>[];
  searchPlaceholder?: string;
  emptyMessage: string;
};

export function DataTable<TData>({
  title,
  description,
  data,
  columns,
  searchPlaceholder = "Search table...",
  emptyMessage,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  // Honour the user's "Table page size" preference (Settings → Data & Refresh).
  const settingsQuery = useUserSettingsQuery();
  const pageSize =
    settingsQuery.data?.table_page_size ?? loadStoredUiSettings()?.table_page_size ?? 10;

  const tableData = useMemo(() => data, [data]);

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table intentionally returns table instance functions.
  const table = useReactTable({
    data: tableData,
    columns,
    state: { sorting, globalFilter },
    initialState: { pagination: { pageSize } },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  useEffect(() => {
    table.setPageSize(pageSize);
  }, [pageSize, table]);

  const resultCount = table.getFilteredRowModel().rows.length;

  return (
    <section className="sx-panel mt-8">
      {/* Header */}
      <div
        className="flex flex-col gap-4 border-b px-5 py-4 lg:flex-row lg:items-center lg:justify-between"
        style={{ borderColor: "var(--sx-border)" }}
      >
        <div>
          <h2
            className="text-base font-semibold"
            style={{ color: "var(--sx-text)", fontFamily: "var(--font-ui)" }}
          >
            {title}
          </h2>
          <p className="mt-0.5 text-sm leading-6" style={{ color: "var(--sx-muted)" }}>
            {description}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            name="table-search"
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder={searchPlaceholder}
            className="sx-input w-full sm:w-72"
          />
          <div
            className="rounded border px-3 py-2 text-sm font-medium tabular-nums"
            style={{
              borderColor: "var(--sx-border-md)",
              background: "var(--sx-bg)",
              color: "var(--sx-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {resultCount} {resultCount === 1 ? "result" : "results"}
          </div>
        </div>
      </div>

      {data.length === 0 ? (
        <p className="px-5 py-8 text-sm" style={{ color: "var(--sx-muted)" }}>
          {emptyMessage}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => {
                      const canSort      = header.column.getCanSort();
                      const sortDirection = header.column.getIsSorted();
                      return (
                        <th
                          key={header.id}
                          className="border-b px-5 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.18em]"
                          style={{
                            borderColor: "var(--sx-border)",
                            color: "var(--sx-dim)",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          {header.isPlaceholder ? null : (
                            <button
                              type="button"
                              onClick={header.column.getToggleSortingHandler()}
                              disabled={!canSort}
                              className={`inline-flex items-center gap-1 transition-colors ${
                                canSort ? "cursor-pointer hover:text-violet-400" : "cursor-default"
                              }`}
                            >
                              {flexRender(header.column.columnDef.header, header.getContext())}
                              {sortDirection === "asc"  && <span>↑</span>}
                              {sortDirection === "desc" && <span>↓</span>}
                            </button>
                          )}
                        </th>
                      );
                    })}
                  </tr>
                ))}
              </thead>

              <tbody>
                {table.getRowModel().rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="px-5 py-8 text-sm"
                      style={{ color: "var(--sx-muted)" }}
                    >
                      No matching records found.
                    </td>
                  </tr>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b transition-colors"
                      style={{ borderColor: "var(--sx-border)" }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLTableRowElement).style.background = "rgba(13,148,136,0.04)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLTableRowElement).style.background = "";
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className="max-w-xl px-5 py-3.5 text-sm"
                          style={{ color: "var(--sx-text)" }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div
            className="flex flex-col gap-3 border-t px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between"
            style={{ borderColor: "var(--sx-border)" }}
          >
            <p className="text-sm" style={{ color: "var(--sx-muted)", fontFamily: "var(--font-mono)" }}>
              Page{" "}
              <span className="font-semibold" style={{ color: "var(--sx-text)" }}>
                {table.getState().pagination.pageIndex + 1}
              </span>{" "}
              of{" "}
              <span className="font-semibold" style={{ color: "var(--sx-text)" }}>
                {table.getPageCount() || 1}
              </span>
            </p>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
                className="sx-button-secondary"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
                className="sx-button-secondary"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
