"""Scout roster — founders and C-suite to track across podcasts.

Each company lists the people whose names we search for in episode titles.
A name appearing in a podcast title = high-confidence guest appearance.
"""

from __future__ import annotations

COMPANIES: list[dict] = [
    # ── Privates ──────────────────────────────────────────────────────────────
    {
        "name": "Anthropic",
        "people": [
            {"name": "Dario Amodei",   "role": "CEO & Co-founder"},
            {"name": "Daniela Amodei", "role": "President & Co-founder"},
        ],
    },
    {
        "name": "OpenAI",
        "people": [
            {"name": "Sam Altman",    "role": "CEO"},
            {"name": "Greg Brockman", "role": "Co-founder"},
        ],
    },
    {
        "name": "Databricks",
        "people": [
            {"name": "Ali Ghodsi", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Stripe",
        "people": [
            {"name": "Patrick Collison", "role": "CEO & Co-founder"},
            {"name": "John Collison",    "role": "President & Co-founder"},
        ],
    },
    {
        "name": "Anduril",
        "people": [
            {"name": "Palmer Luckey", "role": "Founder"},
        ],
    },
    {
        "name": "Figure",
        "people": [
            {"name": "Brett Adcock", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Perplexity",
        "people": [
            {"name": "Aravind Srinivas", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Sierra",
        "people": [
            {"name": "Bret Taylor", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Crusoe",
        "people": [
            {"name": "Chase Lochmiller", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Groq",
        "people": [
            {"name": "Jonathan Ross", "role": "CEO & Founder"},
        ],
    },
    # ── Semiconductors ────────────────────────────────────────────────────────
    {
        "name": "Nvidia",
        "people": [
            {"name": "Jensen Huang", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "TSMC",
        "people": [
            {"name": "C.C. Wei",     "role": "CEO"},
            {"name": "Morris Chang", "role": "Founder"},
        ],
    },
    {
        "name": "Broadcom",
        "people": [
            {"name": "Hock Tan", "role": "CEO"},
        ],
    },
    {
        "name": "Micron",
        "people": [
            {"name": "Sanjay Mehrotra", "role": "CEO"},
        ],
    },
    {
        "name": "AMD",
        "people": [
            {"name": "Lisa Su", "role": "CEO"},
        ],
    },
    {
        "name": "ASML",
        "people": [
            {"name": "Christophe Fouquet", "role": "CEO"},
        ],
    },
    {
        "name": "Intel",
        "people": [
            {"name": "Lip-Bu Tan", "role": "CEO"},
        ],
    },
    {
        "name": "ARM",
        "people": [
            {"name": "Rene Haas", "role": "CEO"},
        ],
    },
    {
        "name": "Lam Research",
        "people": [
            {"name": "Tim Archer", "role": "CEO"},
        ],
    },
    {
        "name": "Applied Materials",
        "people": [
            {"name": "Gary Dickerson", "role": "CEO"},
        ],
    },
    {
        "name": "KLA",
        "people": [
            {"name": "Rick Wallace", "role": "CEO"},
        ],
    },
    {
        "name": "Texas Instruments",
        "people": [
            {"name": "Haviv Ilan", "role": "CEO"},
        ],
    },
    {
        "name": "Marvell",
        "people": [
            {"name": "Matt Murphy", "role": "CEO"},
        ],
    },
    {
        "name": "Qualcomm",
        "people": [
            {"name": "Cristiano Amon", "role": "CEO"},
        ],
    },
    {
        "name": "Analog Devices",
        "people": [
            {"name": "Vincent Roche", "role": "CEO"},
        ],
    },
    {
        "name": "Cadence",
        "people": [
            {"name": "Anirudh Devgan", "role": "CEO"},
        ],
    },
    {
        "name": "Synopsys",
        "people": [
            {"name": "Sassine Ghazi", "role": "CEO"},
        ],
    },
    {
        "name": "NXP",
        "people": [
            {"name": "Kurt Sievers", "role": "CEO"},
        ],
    },
    # ── Mag 7 ─────────────────────────────────────────────────────────────────
    {
        "name": "Apple",
        "people": [
            {"name": "Tim Cook", "role": "CEO"},
        ],
    },
    {
        "name": "Alphabet",
        "people": [
            {"name": "Sundar Pichai", "role": "CEO"},
        ],
    },
    {
        "name": "Microsoft",
        "people": [
            {"name": "Satya Nadella", "role": "CEO"},
        ],
    },
    {
        "name": "Amazon",
        "people": [
            {"name": "Andy Jassy", "role": "CEO"},
        ],
    },
    {
        "name": "Meta",
        "people": [
            {"name": "Mark Zuckerberg", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Tesla",
        "people": [
            {"name": "Elon Musk", "role": "CEO & Founder"},
        ],
    },
    # ── Software ──────────────────────────────────────────────────────────────
    {
        "name": "Oracle",
        "people": [
            {"name": "Larry Ellison", "role": "Founder & CTO"},
            {"name": "Safra Catz",    "role": "CEO"},
        ],
    },
    {
        "name": "Palantir",
        "people": [
            {"name": "Alex Karp",       "role": "CEO & Co-founder"},
            {"name": "Peter Thiel",     "role": "Co-founder"},
        ],
    },
    {
        "name": "Cisco",
        "people": [
            {"name": "Chuck Robbins", "role": "CEO"},
        ],
    },
    {
        "name": "SAP",
        "people": [
            {"name": "Christian Klein", "role": "CEO"},
        ],
    },
    {
        "name": "Salesforce",
        "people": [
            {"name": "Marc Benioff", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "IBM",
        "people": [
            {"name": "Arvind Krishna", "role": "CEO"},
        ],
    },
    {
        "name": "AppLovin",
        "people": [
            {"name": "Adam Foroughi", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "ServiceNow",
        "people": [
            {"name": "Bill McDermott", "role": "CEO"},
        ],
    },
    {
        "name": "Intuit",
        "people": [
            {"name": "Sasan Goodarzi", "role": "CEO"},
        ],
    },
    {
        "name": "Adobe",
        "people": [
            {"name": "Shantanu Narayen", "role": "CEO"},
        ],
    },
    {
        "name": "Shopify",
        "people": [
            {"name": "Tobi Lutke",  "role": "CEO & Founder"},
            {"name": "Tobi Lütke", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Palo Alto Networks",
        "people": [
            {"name": "Nikesh Arora", "role": "CEO"},
        ],
    },
    {
        "name": "CrowdStrike",
        "people": [
            {"name": "George Kurtz", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Snowflake",
        "people": [
            {"name": "Sridhar Ramaswamy", "role": "CEO"},
        ],
    },
    {
        "name": "Fortinet",
        "people": [
            {"name": "Ken Xie", "role": "CEO & Founder"},
        ],
    },
    # ── Internet ──────────────────────────────────────────────────────────────
    {
        "name": "Netflix",
        "people": [
            {"name": "Ted Sarandos", "role": "Co-CEO"},
            {"name": "Greg Peters",  "role": "Co-CEO"},
        ],
    },
    {
        "name": "Uber",
        "people": [
            {"name": "Dara Khosrowshahi", "role": "CEO"},
        ],
    },
    {
        "name": "Booking Holdings",
        "people": [
            {"name": "Glenn Fogel", "role": "CEO"},
        ],
    },
    {
        "name": "Spotify",
        "people": [
            {"name": "Daniel Ek", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "MercadoLibre",
        "people": [
            {"name": "Marcos Galperin", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "DoorDash",
        "people": [
            {"name": "Tony Xu", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Sea Ltd",
        "people": [
            {"name": "Forrest Li", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Airbnb",
        "people": [
            {"name": "Brian Chesky", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "PayPal",
        "people": [
            {"name": "Alex Chriss", "role": "CEO"},
        ],
    },
    {
        "name": "Coupang",
        "people": [
            {"name": "Bom Kim", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Block",
        "people": [
            {"name": "Jack Dorsey", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Roblox",
        "people": [
            {"name": "David Baszucki", "role": "CEO & Founder"},
        ],
    },
    {
        "name": "Robinhood",
        "people": [
            {"name": "Vlad Tenev", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Reddit",
        "people": [
            {"name": "Steve Huffman", "role": "CEO & Co-founder"},
        ],
    },
    {
        "name": "Pinterest",
        "people": [
            {"name": "Bill Ready", "role": "CEO"},
        ],
    },
]
