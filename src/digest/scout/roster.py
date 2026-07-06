"""Scout watchlist — the tracked companies/people the Podscan search runs against.

The watchlist itself lives in the DB (``app_meta["scout_watchlist"]``, edited
from the Scout page in the frontend), not here. This module only holds the
one-time default used to seed that DB row the first time it's empty, plus the
helpers to load and flatten it for ``pipeline.run_cycle``.
"""

from __future__ import annotations

import json

from ..store import repo

_WATCHLIST_META_KEY = "scout_watchlist"

# Ported once from the frontend's WATCHLIST_DEFAULT (frontend/app/scout/page.tsx).
# Only used to seed app_meta the first time the watchlist has never been saved.
DEFAULT_WATCHLIST: list[dict] = [
    {
        "label": "Privates",
        "companies": [
            {"name": "Anthropic", "people": [
                {"name": "Dario Amodei", "role": "CEO & Co-founder"},
                {"name": "Daniela Amodei", "role": "President & Co-founder"},
                {"name": "Tom Brown", "role": "Co-founder"},
                {"name": "Chris Olah", "role": "Co-founder & Research Scientist"},
            ]},
            {"name": "OpenAI", "people": [
                {"name": "Sam Altman", "role": "CEO"},
                {"name": "Greg Brockman", "role": "Co-founder & President"},
                {"name": "Jakub Pachocki", "role": "Chief Scientist"},
                {"name": "Brad Lightcap", "role": "COO"},
            ]},
            {"name": "xAI", "people": [{"name": "Elon Musk", "role": "Founder & CEO"}]},
            {"name": "Databricks", "people": [
                {"name": "Ali Ghodsi", "role": "CEO & Co-founder"},
                {"name": "Ion Stoica", "role": "Co-founder & Executive Chairman"},
                {"name": "Matei Zaharia", "role": "Co-founder & CTO"},
            ]},
            {"name": "Stripe", "people": [
                {"name": "Patrick Collison", "role": "CEO & Co-founder"},
                {"name": "John Collison", "role": "President & Co-founder"},
            ]},
            {"name": "Anduril", "people": [
                {"name": "Palmer Luckey", "role": "Founder"},
                {"name": "Brian Schimpf", "role": "CEO & Co-founder"},
            ]},
            {"name": "Figure", "people": [{"name": "Brett Adcock", "role": "CEO & Founder"}]},
            {"name": "Perplexity", "people": [{"name": "Aravind Srinivas", "role": "CEO & Co-founder"}]},
            {"name": "Sierra", "people": [
                {"name": "Bret Taylor", "role": "CEO & Co-founder"},
                {"name": "Clay Bavor", "role": "Co-founder"},
            ]},
            {"name": "Crusoe", "people": [{"name": "Chase Lochmiller", "role": "CEO & Co-founder"}]},
            {"name": "Groq", "people": [{"name": "Jonathan Ross", "role": "CEO & Founder"}]},
            {"name": "Cohere", "people": [
                {"name": "Aidan Gomez", "role": "CEO & Co-founder"},
                {"name": "Nick Frosst", "role": "Co-founder"},
            ]},
            {"name": "Mistral", "people": [
                {"name": "Arthur Mensch", "role": "CEO & Co-founder"},
                {"name": "Guillaume Lample", "role": "Co-founder"},
            ]},
            {"name": "Scale AI", "people": [{"name": "Alexandr Wang", "role": "CEO & Founder"}]},
            {"name": "Waymo", "people": [
                {"name": "Dmitri Dolgov", "role": "CEO & Co-founder"},
                {"name": "Tekedra Mawakana", "role": "Co-CEO"},
            ]},
            {"name": "SpaceX", "people": [{"name": "Gwynne Shotwell", "role": "President & COO"}]},
        ],
    },
    {
        "label": "Semiconductors",
        "companies": [
            {"name": "Nvidia", "ticker": "NVDA", "people": [
                {"name": "Jensen Huang", "role": "CEO & Co-founder"},
                {"name": "Colette Kress", "role": "CFO"},
                {"name": "Bill Dally", "role": "Chief Scientist"},
            ]},
            {"name": "TSMC", "ticker": "TSM", "people": [
                {"name": "C.C. Wei", "role": "CEO"},
                {"name": "Morris Chang", "role": "Founder"},
            ]},
            {"name": "Broadcom", "ticker": "AVGO", "people": [
                {"name": "Hock Tan", "role": "CEO"},
                {"name": "Kirsten Spears", "role": "CFO"},
            ]},
            {"name": "Micron", "ticker": "MU", "people": [{"name": "Sanjay Mehrotra", "role": "CEO"}]},
            {"name": "AMD", "ticker": "AMD", "people": [
                {"name": "Lisa Su", "role": "CEO"},
                {"name": "Mark Papermaster", "role": "CTO"},
            ]},
            {"name": "ASML", "ticker": "ASML", "people": [
                {"name": "Christophe Fouquet", "role": "CEO"},
                {"name": "Roger Dassen", "role": "CFO"},
            ]},
            {"name": "Intel", "ticker": "INTC", "people": [{"name": "Lip-Bu Tan", "role": "CEO"}]},
            {"name": "ARM", "ticker": "ARM", "people": [{"name": "Rene Haas", "role": "CEO"}]},
            {"name": "Lam Research", "ticker": "LRCX", "people": [{"name": "Tim Archer", "role": "CEO"}]},
            {"name": "Applied Materials", "ticker": "AMAT", "people": [{"name": "Gary Dickerson", "role": "CEO"}]},
            {"name": "KLA", "ticker": "KLAC", "people": [{"name": "Rick Wallace", "role": "CEO"}]},
            {"name": "Texas Instruments", "ticker": "TXN", "people": [{"name": "Haviv Ilan", "role": "CEO"}]},
            {"name": "Marvell", "ticker": "MRVL", "people": [{"name": "Matt Murphy", "role": "CEO"}]},
            {"name": "Qualcomm", "ticker": "QCOM", "people": [{"name": "Cristiano Amon", "role": "CEO"}]},
            {"name": "Analog Devices", "ticker": "ADI", "people": [{"name": "Vincent Roche", "role": "CEO"}]},
            {"name": "Cadence", "ticker": "CDNS", "people": [{"name": "Anirudh Devgan", "role": "CEO"}]},
            {"name": "Synopsys", "ticker": "SNPS", "people": [{"name": "Sassine Ghazi", "role": "CEO"}]},
            {"name": "NXP", "ticker": "NXPI", "people": [{"name": "Kurt Sievers", "role": "CEO"}]},
            {"name": "Mobileye", "ticker": "MBLY", "people": [{"name": "Amnon Shashua", "role": "CEO & Founder"}]},
            {"name": "Lattice Semiconductor", "ticker": "LSCC", "people": [{"name": "Ford Tamer", "role": "CEO"}]},
        ],
    },
    {
        "label": "Mag 7",
        "companies": [
            {"name": "Apple", "ticker": "AAPL", "people": [
                {"name": "Tim Cook", "role": "CEO"},
                {"name": "Jeff Williams", "role": "COO"},
                {"name": "Luca Maestri", "role": "CFO"},
            ]},
            {"name": "Alphabet", "ticker": "GOOGL", "people": [
                {"name": "Sundar Pichai", "role": "CEO"},
                {"name": "Demis Hassabis", "role": "CEO Google DeepMind & Co-founder"},
                {"name": "Ruth Porat", "role": "President & CFO"},
                {"name": "Sergey Brin", "role": "Co-founder"},
                {"name": "Larry Page", "role": "Co-founder"},
            ]},
            {"name": "Microsoft", "ticker": "MSFT", "people": [
                {"name": "Satya Nadella", "role": "CEO"},
                {"name": "Brad Smith", "role": "President & Vice Chair"},
                {"name": "Kevin Scott", "role": "CTO & EVP AI"},
            ]},
            {"name": "Amazon", "ticker": "AMZN", "people": [
                {"name": "Andy Jassy", "role": "CEO"},
                {"name": "Jeff Bezos", "role": "Founder & Executive Chairman"},
                {"name": "Matt Garman", "role": "CEO Amazon Web Services"},
            ]},
            {"name": "Meta", "ticker": "META", "people": [
                {"name": "Mark Zuckerberg", "role": "CEO & Co-founder"},
                {"name": "Yann LeCun", "role": "Chief AI Scientist"},
                {"name": "Andrew Bosworth", "role": "CTO"},
            ]},
            {"name": "Tesla", "ticker": "TSLA", "people": [
                {"name": "Elon Musk", "role": "CEO & Co-founder"},
                {"name": "Vaibhav Taneja", "role": "CFO"},
            ]},
            {"name": "Nvidia", "ticker": "NVDA", "people": [
                {"name": "Jensen Huang", "role": "CEO & Co-founder"},
                {"name": "Colette Kress", "role": "CFO"},
            ]},
        ],
    },
    {
        "label": "Software",
        "companies": [
            {"name": "Oracle", "ticker": "ORCL", "people": [
                {"name": "Larry Ellison", "role": "Founder & CTO"},
                {"name": "Safra Catz", "role": "CEO"},
            ]},
            {"name": "Palantir", "ticker": "PLTR", "people": [
                {"name": "Alex Karp", "role": "CEO & Co-founder"},
                {"name": "Peter Thiel", "role": "Co-founder"},
            ]},
            {"name": "Cisco", "ticker": "CSCO", "people": [{"name": "Chuck Robbins", "role": "CEO"}]},
            {"name": "SAP", "ticker": "SAP", "people": [{"name": "Christian Klein", "role": "CEO"}]},
            {"name": "Salesforce", "ticker": "CRM", "people": [{"name": "Marc Benioff", "role": "CEO & Founder"}]},
            {"name": "IBM", "ticker": "IBM", "people": [{"name": "Arvind Krishna", "role": "CEO"}]},
            {"name": "AppLovin", "ticker": "APP", "people": [{"name": "Adam Foroughi", "role": "CEO & Co-founder"}]},
            {"name": "ServiceNow", "ticker": "NOW", "people": [{"name": "Bill McDermott", "role": "CEO"}]},
            {"name": "Intuit", "ticker": "INTU", "people": [{"name": "Sasan Goodarzi", "role": "CEO"}]},
            {"name": "Adobe", "ticker": "ADBE", "people": [{"name": "Shantanu Narayen", "role": "CEO"}]},
            {"name": "Shopify", "ticker": "SHOP", "people": [
                {"name": "Tobi Lütke", "role": "CEO & Founder"},
                {"name": "Harley Finkelstein", "role": "President"},
            ]},
            {"name": "Palo Alto Networks", "ticker": "PANW", "people": [{"name": "Nikesh Arora", "role": "CEO"}]},
            {"name": "CrowdStrike", "ticker": "CRWD", "people": [{"name": "George Kurtz", "role": "CEO & Co-founder"}]},
            {"name": "Snowflake", "ticker": "SNOW", "people": [{"name": "Sridhar Ramaswamy", "role": "CEO"}]},
            {"name": "Fortinet", "ticker": "FTNT", "people": [{"name": "Ken Xie", "role": "CEO & Founder"}]},
            {"name": "Workday", "ticker": "WDAY", "people": [{"name": "Carl Eschenbach", "role": "CEO"}]},
            {"name": "Datadog", "ticker": "DDOG", "people": [{"name": "Olivier Pomel", "role": "CEO & Co-founder"}]},
            {"name": "MongoDB", "ticker": "MDB", "people": [{"name": "Dev Ittycheria", "role": "CEO"}]},
            {"name": "Cloudflare", "ticker": "NET", "people": [
                {"name": "Matthew Prince", "role": "CEO & Co-founder"},
                {"name": "Michelle Zatlyn", "role": "President & COO & Co-founder"},
            ]},
            {"name": "Confluent", "ticker": "CFLT", "people": [{"name": "Jay Kreps", "role": "CEO & Co-founder"}]},
            {"name": "HashiCorp", "people": [
                {"name": "Armon Dadgar", "role": "Co-founder & CTO"},
                {"name": "Mitchell Hashimoto", "role": "Co-founder"},
            ]},
        ],
    },
    {
        "label": "Internet",
        "companies": [
            {"name": "Netflix", "ticker": "NFLX", "people": [
                {"name": "Ted Sarandos", "role": "Co-CEO"},
                {"name": "Greg Peters", "role": "Co-CEO"},
                {"name": "Reed Hastings", "role": "Co-founder & Executive Chairman"},
            ]},
            {"name": "Uber", "ticker": "UBER", "people": [
                {"name": "Dara Khosrowshahi", "role": "CEO"},
                {"name": "Travis Kalanick", "role": "Co-founder"},
            ]},
            {"name": "Booking Holdings", "ticker": "BKNG", "people": [{"name": "Glenn Fogel", "role": "CEO"}]},
            {"name": "Spotify", "ticker": "SPOT", "people": [{"name": "Daniel Ek", "role": "CEO & Co-founder"}]},
            {"name": "MercadoLibre", "ticker": "MELI", "people": [{"name": "Marcos Galperin", "role": "CEO & Founder"}]},
            {"name": "DoorDash", "ticker": "DASH", "people": [{"name": "Tony Xu", "role": "CEO & Co-founder"}]},
            {"name": "Sea Ltd", "ticker": "SE", "people": [{"name": "Forrest Li", "role": "CEO & Founder"}]},
            {"name": "Airbnb", "ticker": "ABNB", "people": [
                {"name": "Brian Chesky", "role": "CEO & Co-founder"},
                {"name": "Joe Gebbia", "role": "Co-founder"},
                {"name": "Nathan Blecharczyk", "role": "Co-founder & Chief Strategy Officer"},
            ]},
            {"name": "PayPal", "ticker": "PYPL", "people": [
                {"name": "Alex Chriss", "role": "CEO"},
                {"name": "Peter Thiel", "role": "Co-founder"},
            ]},
            {"name": "Coupang", "ticker": "CPNG", "people": [{"name": "Bom Kim", "role": "CEO & Founder"}]},
            {"name": "Block", "ticker": "XYZ", "people": [{"name": "Jack Dorsey", "role": "CEO & Founder"}]},
            {"name": "Roblox", "ticker": "RBLX", "people": [{"name": "David Baszucki", "role": "CEO & Founder"}]},
            {"name": "Robinhood", "ticker": "HOOD", "people": [
                {"name": "Vlad Tenev", "role": "CEO & Co-founder"},
                {"name": "Baiju Bhatt", "role": "Co-founder"},
            ]},
            {"name": "Reddit", "ticker": "RDDT", "people": [{"name": "Steve Huffman", "role": "CEO & Co-founder"}]},
            {"name": "Pinterest", "ticker": "PINS", "people": [
                {"name": "Bill Ready", "role": "CEO"},
                {"name": "Ben Silbermann", "role": "Co-founder & Executive Chairman"},
            ]},
            {"name": "Lyft", "ticker": "LYFT", "people": [{"name": "David Risher", "role": "CEO"}]},
            {"name": "Instacart", "ticker": "CART", "people": [{"name": "Fidji Simo", "role": "CEO"}]},
            {"name": "Duolingo", "ticker": "DUOL", "people": [{"name": "Luis von Ahn", "role": "CEO & Co-founder"}]},
        ],
    },
]


def load_watchlist(conn) -> list[dict]:
    """Return the saved watchlist, seeding it with DEFAULT_WATCHLIST the first time."""
    raw = repo.meta_get(conn, _WATCHLIST_META_KEY)
    if raw:
        try:
            return json.loads(raw)
        except ValueError:
            pass
    repo.meta_set(conn, _WATCHLIST_META_KEY, json.dumps(DEFAULT_WATCHLIST))
    return DEFAULT_WATCHLIST


def save_watchlist(conn, watchlist: list[dict]) -> None:
    repo.meta_set(conn, _WATCHLIST_META_KEY, json.dumps(watchlist))


def flatten_watchlist(categories: list[dict]) -> list[tuple[str, str, str]]:
    """Flatten to (company, person_name, person_role) triples for Podscan search.

    Dedupes by person name (case-insensitive), keeping the first company a name
    is encountered under, since Podscan searches by name only and a full scan
    costs one request per unique person against a 100/day quota.
    """
    seen: dict[str, tuple[str, str, str]] = {}
    for category in categories:
        for company in category.get("companies", []):
            company_name = company.get("name", "")
            for person in company.get("people", []):
                name = person.get("name", "")
                if not name:
                    continue
                key = name.strip().lower()
                if key in seen:
                    continue
                seen[key] = (company_name, name, person.get("role", ""))
    return list(seen.values())
