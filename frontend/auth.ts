import NextAuth from "next-auth";
import type { Provider } from "next-auth/providers";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

// Auth.js with JWT sessions and no adapter: the backend `users` table is the
// system of record. On sign-in we upsert the user there and carry its id +
// admin flag in the token; proxy.ts forwards the id to the backend as X-User-Id.

const BACKEND = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

/** Local-only "sign in as any email" for testing multi-user flows without an
 * OAuth client. Never enabled in production builds. */
export const DEV_LOGIN =
  process.env.NODE_ENV !== "production" && process.env.AUTH_DEV_LOGIN === "1";

const providers: Provider[] = [Google];
if (DEV_LOGIN) {
  providers.push(
    Credentials({
      id: "dev",
      name: "Dev login",
      credentials: { email: { label: "Email", type: "email" } },
      authorize: (c) => {
        const email = String(c?.email ?? "").trim();
        return email.includes("@") ? { email, name: email.split("@")[0] } : null;
      },
    }),
  );
}

async function upsertBackendUser(u: {
  email: string;
  name?: string | null;
  image?: string | null;
  provider?: string;
  providerAccountId?: string;
}): Promise<{ id: number; is_admin: boolean }> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (process.env.DIGEST_API_KEY) headers["x-api-key"] = process.env.DIGEST_API_KEY;
  const res = await fetch(`${BACKEND}/api/auth/upsert-user`, {
    method: "POST",
    headers,
    cache: "no-store",
    body: JSON.stringify({
      email: u.email,
      name: u.name ?? null,
      image: u.image ?? null,
      provider: u.provider ?? null,
      provider_account_id: u.providerAccountId ?? null,
    }),
  });
  if (!res.ok) throw new Error(`user upsert failed: ${res.status}`);
  return res.json();
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  trustHost: true,
  callbacks: {
    async jwt({ token, user, account }) {
      // `account` is only present on the sign-in request.
      if (account && user?.email) {
        const backendUser = await upsertBackendUser({
          email: user.email,
          name: user.name,
          image: user.image,
          provider: account.provider,
          providerAccountId: account.providerAccountId,
        });
        token.uid = backendUser.id;
        token.isAdmin = backendUser.is_admin;
      }
      return token;
    },
    session({ session, token }) {
      if (token.uid != null) session.user.id = String(token.uid);
      session.user.isAdmin = !!token.isAdmin;
      return session;
    },
  },
});
