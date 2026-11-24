import test from "node:test";
import assert from "node:assert/strict";
import { validateProfileUpdateInput, validatePasswordChangeInput } from "../src/validators/auth.validator.js";
import { updateProfile, changePassword } from "../src/controllers/auth.controller.js";

function response() {
  return { statusCode: null, body: null, status(c) { this.statusCode = c; return this; }, json(b) { this.body = b; return this; } };
}

test("profile validator accepts a small image data URL and HTTPS avatar", () => {
  const dataUrl = `data:image/png;base64,${Buffer.from("tiny").toString("base64")}`;
  const parsed = validateProfileUpdateInput({ avatarUrl: dataUrl });
  assert.equal(parsed.isValid, true);
  assert.equal(parsed.sanitized.avatarUrl, dataUrl);
  const https = validateProfileUpdateInput({ avatarUrl: "https://example.com/a.png" });
  assert.equal(https.isValid, true);
  const bad = validateProfileUpdateInput({ avatarUrl: "http://insecure/a.png" });
  assert.equal(bad.isValid, false);
});

test("password change validator enforces current and strong new password", () => {
  assert.equal(validatePasswordChangeInput({ currentPassword: "old-password", newPassword: "short" }).isValid, false);
  assert.equal(validatePasswordChangeInput({ currentPassword: "same", newPassword: "same" }).isValid, false);
  assert.equal(validatePasswordChangeInput({ currentPassword: "old-password", newPassword: "new-strong-password" }).isValid, true);
});

test("updateProfile persists avatarUrl", async () => {
  const user = {
    _id: "u1", name: "Farmer", phone: "+8801712345678", phoneVerifiedAt: new Date(),
    avatarUrl: null, async save() { this.saved = true; },
  };
  const res = response();
  await updateProfile({ user, body: { avatarUrl: "https://example.com/a.png" } }, res);
  assert.equal(res.statusCode, 200);
  assert.equal(user.avatarUrl, "https://example.com/a.png");
  assert.equal(user.saved, true);
});

test("changePassword verifies current password and rejects wrong one", async () => {
  const user = {
    _id: "u1", authProvider: "local",
    async comparePassword(p) { return p === "correct-old"; },
  };
  const originalFind = (await import("../src/models/user.model.js")).User.findById;
  const User = (await import("../src/models/user.model.js")).User;
  User.findById = () => ({ select: async () => ({
    ...user,
    passwordHash: "hash",
    async save() { this.saved = true; },
  }) });
  try {
    const wrong = response();
    await changePassword({ user: { _id: "u1" }, body: { currentPassword: "wrong", newPassword: "new-strong-password" } }, wrong);
    assert.equal(wrong.body.error.code, "INVALID_CURRENT_PASSWORD");

    const ok = response();
    await changePassword({ user: { _id: "u1" }, body: { currentPassword: "correct-old", newPassword: "new-strong-password" } }, ok);
    assert.equal(ok.statusCode, 200);
  } finally {
    User.findById = originalFind;
  }
});
