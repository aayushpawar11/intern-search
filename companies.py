"""
Company monitoring list.

Add a company: copy a nearby Company(...) block and fill in name/source/slug.
Remove a company: delete the block, or set enabled=False.
Commenting a block out also works.

Sources (public career-board APIs, not LinkedIn scraping):
  greenhouse, lever, ashby, workday, rippling, amazon, eightfold, phenom,
  google, apple, meta, tesla, tiktok, avature, workable, jibe, tinder, html
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Company:
    name: str
    source: str
    slug: str = ""
    careers_url: str = ""
    extra: dict = field(default_factory=dict)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Edit this list. Duplicate names (Cisco, Dell) appear only once.
# Groq and X were removed per request.
# ---------------------------------------------------------------------------
COMPANIES: list[Company] = [
    Company(
        name="Microsoft",
        source="microsoft",
        careers_url=(
            "https://apply.careers.microsoft.com/careers?start=0"
            "&location=United+States%2C+Multiple+Locations%2C+Multiple+Locations"
            "&pid=1970393556959254&sort_by=timestamp"
            "&filter_include_remote=1&filter_include_relocation=0"
        ),
        extra={"query": "intern"},
    ),
    Company(
        name="Google",
        source="google",
        careers_url=(
            "https://www.google.com/about/careers/applications/jobs/results"
            "?location=United%20States&target_level=INTERN_AND_APPRENTICE&sort_by=date"
        ),
    ),
    Company(
        name="Amazon",
        source="amazon",
        careers_url="https://www.amazon.jobs/en/search?base_query=software+engineer+intern",
        extra={"query": "software engineer intern"},
    ),
    Company(
        name="Apple",
        source="apple",
        careers_url="https://jobs.apple.com/en-us/search?search=intern%20software&sort=newest",
        extra={"query": "intern software"},
    ),
    Company(
        name="Nvidia",
        source="workday",
        slug="nvidia",
        careers_url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        extra={"tenant": "nvidia", "dc": "wd5", "site": "NVIDIAExternalCareerSite"},
    ),
    Company(
        name="Meta",
        source="meta",
        careers_url="https://www.metacareers.com/jobs?roles[0]=Internship&sort_by_new=true",
        extra={"doc_id": "27129360303422352"},
    ),
    Company(
        name="Tesla",
        source="tesla",
        careers_url="https://www.tesla.com/careers/search/?type=intern&site=US",
    ),
    Company(
        name="Palantir",
        source="lever",
        slug="palantir",
        careers_url="https://jobs.lever.co/palantir",
    ),
    Company(
        name="Netflix",
        source="eightfold",
        careers_url="https://explore.jobs.netflix.net/careers",
        extra={
            "api": "https://explore.jobs.netflix.net/api/apply/v2/jobs",
            "domain": "netflix.com",
            "query": "intern software",
        },
    ),
    Company(
        name="Uber",
        source="workday",
        slug="uber",
        careers_url="https://www.uber.com/careers/list/?query=intern",
        extra={"tenant": "uber", "dc": "wd1", "site": "External"},
    ),
    Company(
        name="Waymo",
        source="greenhouse",
        slug="waymo",
        careers_url="https://boards.greenhouse.io/waymo",
    ),
    Company(
        name="Ramp",
        source="ashby",
        slug="ramp",
        careers_url="https://jobs.ashbyhq.com/ramp",
    ),
    Company(
        name="Coinbase",
        source="greenhouse",
        slug="coinbase",
        careers_url="https://boards.greenhouse.io/coinbase",
    ),
    Company(
        name="Databricks",
        source="greenhouse",
        slug="databricks",
        careers_url="https://boards.greenhouse.io/databricks",
    ),
    Company(
        name="OpenAI",
        source="ashby",
        slug="openai",
        careers_url="https://jobs.ashbyhq.com/openai",
    ),
    Company(
        name="Lyft",
        source="greenhouse",
        slug="lyft",
        careers_url="https://boards.greenhouse.io/lyft",
    ),
    Company(
        name="DoorDash",
        source="greenhouse",
        slug="doordashusa",
        careers_url="https://job-boards.greenhouse.io/doordashusa",
    ),
    Company(
        name="LinkedIn",
        source="greenhouse",
        slug="linkedin",
        careers_url="https://boards.greenhouse.io/linkedin",
    ),
    Company(
        name="Datadog",
        source="greenhouse",
        slug="datadog",
        careers_url="https://boards.greenhouse.io/datadog",
    ),
    Company(
        name="Snap",
        source="workday",
        slug="snapchat",
        careers_url="https://careers.snap.com/jobs",
        extra={"tenant": "snapchat", "dc": "wd1", "site": "SNAP"},
    ),
    Company(
        name="Stripe",
        source="greenhouse",
        slug="stripe",
        careers_url="https://boards.greenhouse.io/stripe",
    ),
    Company(
        name="Robinhood",
        source="greenhouse",
        slug="robinhood",
        careers_url="https://boards.greenhouse.io/robinhood",
    ),
    Company(
        name="Square",
        source="greenhouse",
        slug="block",
        careers_url="https://boards.greenhouse.io/block",
    ),
    Company(
        name="Figma",
        source="greenhouse",
        slug="figma",
        careers_url="https://boards.greenhouse.io/figma",
    ),
    Company(
        name="Qualcomm",
        source="workday",
        slug="qualcomm",
        careers_url="https://qualcomm.wd5.myworkdayjobs.com/External",
        extra={"tenant": "qualcomm", "dc": "wd5", "site": "External"},
    ),
    Company(
        name="Spotify",
        source="lever",
        slug="spotify",
        careers_url="https://jobs.lever.co/spotify",
    ),
    Company(
        name="Anthropic",
        source="greenhouse",
        slug="anthropic",
        careers_url="https://boards.greenhouse.io/anthropic",
    ),
    Company(
        name="Cohere",
        source="ashby",
        slug="cohere",
        careers_url="https://jobs.ashbyhq.com/cohere",
    ),
    Company(
        name="ScaleAI",
        source="greenhouse",
        slug="scaleai",
        careers_url="https://boards.greenhouse.io/scaleai",
    ),
    Company(
        name="Snowflake",
        source="ashby",
        slug="snowflake",
        careers_url="https://jobs.ashbyhq.com/snowflake",
    ),
    Company(
        name="TikTok",
        source="tiktok",
        careers_url=(
            "https://lifeattiktok.com/search?recruitment_id_list=202%2C301"
            "&job_category_id_list=&subject_id_list=&location_code_list="
            "&keyword=&limit=12&offset=0"
        ),
        extra={"recruitment_ids": ["202", "301"]},
    ),
    Company(
        name="Verkada",
        source="greenhouse",
        slug="verkada",
        careers_url="https://boards.greenhouse.io/verkada",
    ),
    Company(
        name="Anduril",
        source="greenhouse",
        slug="andurilindustries",
        careers_url="https://boards.greenhouse.io/andurilindustries",
    ),
    Company(
        name="Bloomberg",
        source="avature",
        careers_url=(
            "https://bloomberg.avature.net/careers/SearchJobs/"
            "?1686=%5B55479%5D&1686_format=2312&listFilterMode=1&jobRecordsPerPage=12"
        ),
    ),
    Company(
        name="Airbnb",
        source="greenhouse",
        slug="airbnb",
        careers_url="https://boards.greenhouse.io/airbnb",
    ),
    Company(
        name="Roblox",
        source="greenhouse",
        slug="roblox",
        careers_url="https://boards.greenhouse.io/roblox",
    ),
    Company(
        name="Dropbox",
        source="greenhouse",
        slug="dropbox",
        careers_url="https://boards.greenhouse.io/dropbox",
    ),
    Company(
        name="Pinterest",
        source="greenhouse",
        slug="pinterest",
        careers_url="https://boards.greenhouse.io/pinterest",
    ),
    Company(
        name="Notion",
        source="ashby",
        slug="notion",
        careers_url="https://jobs.ashbyhq.com/notion",
    ),
    Company(
        name="Adobe",
        source="workday",
        slug="adobe",
        careers_url="https://adobe.wd5.myworkdayjobs.com/external_experienced",
        extra={"tenant": "adobe", "dc": "wd5", "site": "external_experienced"},
    ),
    Company(
        name="Salesforce",
        source="workday",
        slug="salesforce",
        careers_url="https://salesforce.wd12.myworkdayjobs.com/External_Career_Site",
        extra={"tenant": "salesforce", "dc": "wd12", "site": "External_Career_Site"},
    ),
    Company(
        name="Intuit",
        source="workday",
        slug="intuit",
        careers_url="https://intuit.wd5.myworkdayjobs.com/Intuit_Careers",
        extra={"tenant": "intuit", "dc": "wd5", "site": "Intuit_Careers"},
    ),
    Company(
        name="Workday",
        source="workday",
        slug="workday",
        careers_url="https://workday.wd5.myworkdayjobs.com/Workday",
        extra={"tenant": "workday", "dc": "wd5", "site": "Workday"},
    ),
    Company(
        name="SpaceX",
        source="greenhouse",
        slug="spacex",
        careers_url="https://boards.greenhouse.io/spacex",
    ),
    Company(
        name="MongoDB",
        source="greenhouse",
        slug="mongodb",
        careers_url="https://boards.greenhouse.io/mongodb",
    ),
    Company(
        name="GitHub",
        source="phenom",
        careers_url="https://www.github.careers/careers",
        extra={"api": "https://www.github.careers/api/jobs"},
    ),
    Company(
        name="GitLab",
        source="greenhouse",
        slug="gitlab",
        careers_url="https://boards.greenhouse.io/gitlab",
    ),
    Company(
        name="Vercel",
        source="greenhouse",
        slug="vercel",
        careers_url="https://boards.greenhouse.io/vercel",
    ),
    Company(
        name="ServiceNow",
        source="workday",
        slug="servicenow",
        careers_url="https://servicenow.wd1.myworkdayjobs.com/servicenow",
        extra={"tenant": "servicenow", "dc": "wd1", "site": "servicenow"},
    ),
    Company(
        name="CrowdStrike",
        source="workday",
        slug="crowdstrike",
        careers_url="https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers",
        extra={"tenant": "crowdstrike", "dc": "wd5", "site": "crowdstrikecareers"},
    ),
    Company(
        name="Okta",
        source="greenhouse",
        slug="okta",
        careers_url="https://boards.greenhouse.io/okta",
    ),
    Company(
        name="Oracle",
        source="workday",
        slug="oracle",
        careers_url="https://oracle.wd1.myworkdayjobs.com/Careers",
        extra={"tenant": "oracle", "dc": "wd1", "site": "Careers"},
    ),
    Company(
        name="Plaid",
        source="ashby",
        slug="plaid",
        careers_url="https://jobs.ashbyhq.com/plaid",
    ),
    Company(
        name="Affirm",
        source="greenhouse",
        slug="affirm",
        careers_url="https://boards.greenhouse.io/affirm",
    ),
    Company(
        name="Chime",
        source="greenhouse",
        slug="chime",
        careers_url="https://boards.greenhouse.io/chime",
    ),
    Company(
        name="Brex",
        source="greenhouse",
        slug="brex",
        careers_url="https://boards.greenhouse.io/brex",
    ),
    Company(
        name="Mercury",
        source="greenhouse",
        slug="mercury",
        careers_url="https://boards.greenhouse.io/mercury",
    ),
    Company(
        name="AMD",
        source="workday",
        slug="amd",
        careers_url="https://amd.wd1.myworkdayjobs.com/AMD",
        extra={"tenant": "amd", "dc": "wd1", "site": "AMD"},
    ),
    Company(
        name="Rippling",
        source="rippling",
        slug="rippling",
        careers_url="https://www.rippling.com/careers/open-roles",
    ),
    Company(
        name="Dell",
        source="workday",
        slug="dell",
        careers_url="https://dell.wd1.myworkdayjobs.com/External",
        extra={"tenant": "dell", "dc": "wd1", "site": "External"},
    ),
    Company(
        name="Capital One",
        source="workday",
        slug="capitalone",
        careers_url="https://capitalone.wd1.myworkdayjobs.com/Capital_One",
        extra={"tenant": "capitalone", "dc": "wd1", "site": "Capital_One"},
    ),
    Company(
        name="SAP",
        source="workday",
        slug="sap",
        careers_url="https://sap.wd1.myworkdayjobs.com/SAPCareers",
        extra={"tenant": "sap", "dc": "wd1", "site": "SAPCareers"},
    ),
    Company(
        name="Cisco",
        source="workday",
        slug="cisco",
        careers_url="https://cisco.wd1.myworkdayjobs.com/Cisco_Careers",
        extra={"tenant": "cisco", "dc": "wd1", "site": "Cisco_Careers"},
    ),
    Company(
        name="Garmin",
        source="workday",
        slug="garmin",
        careers_url="https://careers.garmin.com",
        extra={"tenant": "garmin", "dc": "wd5", "site": "garmin"},
    ),
    Company(
        name="Walmart Global Tech",
        source="workday",
        slug="walmart",
        careers_url="https://walmart.wd5.myworkdayjobs.com/WalmartExternal",
        extra={"tenant": "walmart", "dc": "wd5", "site": "WalmartExternal"},
    ),
    Company(
        name="Intel",
        source="workday",
        slug="intel",
        careers_url="https://intel.wd1.myworkdayjobs.com/External",
        extra={"tenant": "intel", "dc": "wd1", "site": "External"},
    ),
    Company(
        name="Splunk",
        source="workday",
        slug="splunk",
        careers_url="https://splunk.wd1.myworkdayjobs.com/splunk",
        extra={"tenant": "splunk", "dc": "wd1", "site": "splunk"},
    ),
    Company(
        name="AIQ Markets",
        source="html",
        careers_url="https://www.linkedin.com/company/aiqmarkets/",
        extra={"note": "LinkedIn company pages usually block scrapers; swap in a real careers URL if they publish one."},
        enabled=False,
    ),
    Company(
        name="Slack",
        source="workday",
        slug="salesforce",
        careers_url="https://salesforce.wd12.myworkdayjobs.com/Slack",
        extra={"tenant": "salesforce", "dc": "wd12", "site": "Slack"},
    ),
    Company(
        name="PayPal",
        source="workday",
        slug="paypal",
        careers_url="https://paypal.wd1.myworkdayjobs.com/jobs",
        extra={"tenant": "paypal", "dc": "wd1", "site": "jobs"},
    ),
    Company(
        name="Twitch",
        source="greenhouse",
        slug="twitch",
        careers_url="https://boards.greenhouse.io/twitch",
    ),
    Company(
        name="Replit",
        source="ashby",
        slug="replit",
        careers_url="https://jobs.ashbyhq.com/replit",
    ),
    Company(
        name="Atlassian",
        source="atlassian",
        careers_url="https://www.atlassian.com/company/careers/all-jobs?team=&location=United%20States&search=",
    ),
    Company(
        name="Discord",
        source="greenhouse",
        slug="discord",
        careers_url="https://boards.greenhouse.io/discord",
    ),
    Company(
        name="OpenClaw",
        source="html",
        careers_url="https://www.openclaw.org/careers",
    ),
    Company(
        name="LangChain",
        source="ashby",
        slug="langchain",
        careers_url="https://jobs.ashbyhq.com/langchain",
    ),
    Company(
        name="Palo Alto Networks",
        source="workday",
        slug="paloaltonetworks",
        careers_url="https://jobs.paloaltonetworks.com",
        extra={"tenant": "paloaltonetworks", "dc": "wd5", "site": "External_Career_Site"},
    ),
    Company(
        name="Asana",
        source="greenhouse",
        slug="asana",
        careers_url="https://asana.com/jobs/all",
    ),
    Company(
        name="Duolingo",
        source="greenhouse",
        slug="duolingo",
        careers_url="https://careers.duolingo.com/#careers",
    ),
    Company(
        name="Cloudflare",
        source="greenhouse",
        slug="cloudflare",
        careers_url="https://www.cloudflare.com/careers/jobs/",
    ),
    Company(
        name="Hugging Face",
        source="workable",
        slug="huggingface",
        careers_url="https://apply.workable.com/huggingface/#jobs",
    ),
    Company(
        name="HubSpot",
        source="html",
        careers_url=(
            "https://www.hubspot.com/careers/jobs"
            "?page=1#office=san-francisco,remote;department=product-ux-engineering;"
        ),
        extra={"note": "Careers GraphQL is Cloudflare-blocked; HTML fallback until a public JSON feed exists."},
    ),
    Company(
        name="Patreon",
        source="ashby",
        slug="patreon",
        careers_url="https://jobs.ashbyhq.com/patreon",
    ),
    Company(
        name="DocuSign",
        source="jibe",
        careers_url="https://careers.docusign.com/careers-home/jobs",
        extra={
            "api": "https://careers.docusign.com/api/jobs",
            "query": "intern",
            "job_url_base": "https://careers.docusign.com/careers-home/jobs",
        },
    ),
    Company(
        name="Reddit",
        source="greenhouse",
        slug="reddit",
        careers_url="https://redditinc.com/careers",
    ),
    Company(
        name="SeatGeek",
        source="greenhouse",
        slug="seatgeek",
        careers_url="https://seatgeek.com/jobs?departments=softwareengineering&locations=all",
    ),
    Company(
        name="Lattice",
        source="greenhouse",
        slug="lattice",
        careers_url="https://lattice.com/job",
    ),
    Company(
        name="Tinder",
        source="tinder",
        careers_url="https://www.lifeattinder.com/positions?department=engineering",
    ),
]


def enabled_companies() -> list[Company]:
    return [c for c in COMPANIES if c.enabled]
