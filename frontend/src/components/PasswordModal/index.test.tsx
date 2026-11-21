import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { authenticate, AuthError } from "../../api/auth";
import PasswordModal from "./index";

vi.mock("../../api/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/auth")>();
  return { ...actual, authenticate: vi.fn() };
});

const mockedAuthenticate = vi.mocked(authenticate);

describe("PasswordModal", () => {
  beforeEach(() => mockedAuthenticate.mockReset());

  it("authenticates and resumes the gated action", async () => {
    const onSuccess = vi.fn();
    mockedAuthenticate.mockResolvedValue();
    render(<PasswordModal onSuccess={onSuccess} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));

    await waitFor(() => expect(mockedAuthenticate).toHaveBeenCalledWith("secret"));
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("shows authentication failures and supports cancellation", async () => {
    const onCancel = vi.fn();
    mockedAuthenticate.mockRejectedValueOnce(new AuthError("Wrong password"));
    render(<PasswordModal onSuccess={vi.fn()} onCancel={onCancel} />);

    fireEvent.change(screen.getByPlaceholderText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));

    expect(await screen.findByText("Wrong password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toHaveValue("");

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
