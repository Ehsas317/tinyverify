"""Registry configuration: where the official page lives, who reads it."""

REGISTRIES = {
    "UK Companies House": {
        "jurisdiction": "UK",
        "reader": "Fetch",
        "search_url": "https://find-and-update.company-information.service.gov.uk/search?q={q}",
        "official_domains": ["gov.uk"],
    },
    "US SEC EDGAR": {
        "jurisdiction": "US",
        "reader": "Fetch",
        "search_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}&type=10-K&count=5",
        "official_domains": ["sec.gov"],
    },
    "UK FCA Financial Services Register": {
        "jurisdiction": "UK",
        "reader": "Agent",  # Fetch: target_unreachable (verified 2026-11-08)
        "search_url": "https://register.fca.org.uk/s/firm?q={q}",
        "official_domains": ["fca.org.uk"],
    },
}
