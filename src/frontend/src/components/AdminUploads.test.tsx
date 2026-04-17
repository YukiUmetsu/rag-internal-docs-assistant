import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { AdminUploads } from "./AdminUploads";
import { listAdminUploads, uploadAdminFiles } from "../api/admin";

vi.mock("../api/admin", () => ({
  listAdminUploads: vi.fn(),
  uploadAdminFiles: vi.fn(),
}));

const EMPTY_PAGE = {
  items: [],
  total: 0,
  limit: 5,
  offset: 0,
};

beforeEach(() => {
  vi.mocked(listAdminUploads).mockResolvedValue(EMPTY_PAGE);
  vi.mocked(uploadAdminFiles).mockResolvedValue([
    {
      id: "upload-1",
      original_filename: "sample.md",
      stored_path: "/tmp/sample.md",
      content_type: "text/markdown",
      file_size_bytes: 12,
      checksum: "abc123",
      created_at: "2026-04-16T12:00:00.000Z",
      updated_at: "2026-04-16T12:00:00.000Z",
    },
  ]);
});

it("uploads selected files and keeps the success message visible", async () => {
  const { container } = render(<AdminUploads />);

  await waitFor(() => expect(listAdminUploads).toHaveBeenCalledTimes(1));

  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).not.toBeNull();

  const selectedFile = new File(["# Upload"], "sample.md", { type: "text/markdown" });
  fireEvent.change(input as HTMLInputElement, {
    target: { files: [selectedFile] },
  });

  expect(screen.getByText("1 file selected")).toBeTruthy();
  expect(screen.getByText("sample.md")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Upload selected" }));

  await waitFor(() => expect(uploadAdminFiles).toHaveBeenCalledTimes(1));
  expect(uploadAdminFiles).toHaveBeenCalledWith([selectedFile]);

  await waitFor(() => expect(screen.getByText("Uploaded 1 file.")).toBeTruthy());
  await waitFor(() => expect(listAdminUploads).toHaveBeenCalledTimes(2));
});
