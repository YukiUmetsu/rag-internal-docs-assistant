import { expect, it, vi } from "vitest";

import { uploadAdminFiles } from "./admin";
import { requestFormData } from "./request";

vi.mock("./request", () => ({
  requestFormData: vi.fn(),
  requestJson: vi.fn(),
}));

it("uploads admin files as multipart form data", async () => {
  const firstFile = new File(["# One"], "one.md", { type: "text/markdown" });
  const secondFile = new File(["# Two"], "two.pdf", { type: "application/pdf" });
  vi.mocked(requestFormData).mockResolvedValueOnce([]);

  await uploadAdminFiles([firstFile, secondFile]);

  expect(requestFormData).toHaveBeenCalledTimes(1);
  const [path, formData, init] = vi.mocked(requestFormData).mock.calls[0];
  expect(path).toBe("/api/ingest/uploads");
  expect(init?.method).toBe("POST");
  expect((formData as FormData).getAll("files")).toHaveLength(2);
  expect((formData as FormData).getAll("files")[0]).toBe(firstFile);
  expect((formData as FormData).getAll("files")[1]).toBe(secondFile);
});
