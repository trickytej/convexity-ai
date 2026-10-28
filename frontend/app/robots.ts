import type { MetadataRoute } from "next";

// Crawlers may index the marketing pages only. Every other page renders live
// data from the database, and bots walking the public demo (69 model pages,
// thousands of episodes) exhausted the Turso read quota in Oct 2026.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/$", "/about", "/pro"], disallow: "/" }],
  };
}
