"""Semantic route definitions with representative utterances."""

from __future__ import annotations

from semantic_router import Route

# ── Finance Route ───────────────────────────────────────────────────────────

finance_route = Route(
    name="finance_route",
    utterances=[
        "What was our total revenue last quarter?",
        "Show me the budget allocation for 2026",
        "What are the key financial metrics from the annual report?",
        "How much did we spend on R&D last year?",
        "What is our current burn rate?",
        "Can you summarize the investor presentation highlights?",
        "What were the profit margins by product line?",
        "How does our revenue compare quarter over quarter?",
        "What are the projected expenses for next fiscal year?",
        "Summarize the latest earnings call key takeaways",
        "What is our debt-to-equity ratio?",
        "Break down the operating costs by department",
        "How much payment was given to vendor Amazon Web Services?",
        "What is the total payment for Microsoft Azure?",
        "Show me vendor payment summaries",
        "Who are our top paid vendors?",
        "How much did we pay for cloud infrastructure?",
    ],
    metadata={
        "target_collection": "finance",
        "required_roles": ["finance_analyst", "executive"],
        "description": "Queries about revenue, budgets, financial metrics, investor info",
    },
)

# ── Engineering Route ───────────────────────────────────────────────────────

engineering_route = Route(
    name="engineering_route",
    utterances=[
        "Explain the microservices architecture overview",
        "What APIs are available for the payment service?",
        "Summarize the recent production incident report",
        "What is our deployment pipeline process?",
        "How is the authentication system designed?",
        "What technology stack do we use for the backend?",
        "List the API endpoints for the user management service",
        "What were the root causes of the last outage?",
        "Describe the database schema for the orders table",
        "What are our system reliability SLAs?",
        "How do we handle API rate limiting?",
        "What is the disaster recovery plan for our infrastructure?",
    ],
    metadata={
        "target_collection": "engineering",
        "required_roles": ["engineer", "executive"],
        "description": "Queries about systems, architecture, APIs, incidents, code",
    },
)

# ── Marketing Route ─────────────────────────────────────────────────────────

marketing_route = Route(
    name="marketing_route",
    utterances=[
        "What were the results of our Q1 marketing campaign?",
        "Summarize the brand guidelines for social media",
        "How has our market share changed over the last year?",
        "What are the key takeaways from the competitor analysis?",
        "Describe our target customer segments",
        "What was the ROI on the last digital ad campaign?",
        "What is our content marketing strategy for this quarter?",
        "How is our brand perceived compared to competitors?",
        "What channels drive the most customer acquisition?",
        "Summarize the latest customer satisfaction survey results",
        "What is our social media engagement rate trend?",
        "What marketing budget was allocated for product launches?",
    ],
    metadata={
        "target_collection": "marketing",
        "required_roles": ["marketing_specialist", "executive"],
        "description": "Queries about campaigns, brand, market share, competitors",
    },
)

# ── HR General Route ────────────────────────────────────────────────────────

hr_general_route = Route(
    name="hr_general_route",
    utterances=[
        "What is the company's leave policy?",
        "How do I apply for parental leave?",
        "What health benefits are available to employees?",
        "Describe the employee onboarding process",
        "What is the company's remote work policy?",
        "How does the performance review process work?",
        "What are the guidelines for reporting workplace harassment?",
        "What professional development programs are available?",
        "Explain the company's code of conduct",
        "How many sick days am I entitled to per year?",
        "What is the process for requesting a role transfer?",
        "What diversity and inclusion initiatives does the company have?",
    ],
    metadata={
        "target_collection": "hr",
        "required_roles": ["employee", "hr_representative", "executive"],
        "description": "Queries about policies, leave, benefits, company culture",
    },
)

# ── Cross Department Route ──────────────────────────────────────────────────

cross_department_route = Route(
    name="cross_department_route",
    utterances=[
        "Give me an overview of the company's performance this year",
        "What are the company's strategic priorities for 2026?",
        "Summarize the company handbook",
        "What are the most important updates across all departments?",
        "How is the company doing overall?",
        "What are the key initiatives planned for next quarter?",
        "Tell me about the company's mission and values",
        "What changes were announced in the last all-hands meeting?",
        "How does our company compare to industry benchmarks?",
        "What are the upcoming company-wide events?",
        "Summarize the CEO's quarterly message",
        "What new policies were introduced this year?",
    ],
    metadata={
        "target_collection": "cross_department",
        "required_roles": [
            "employee",
            "finance_analyst",
            "engineer",
            "marketing_specialist",
            "executive",
            "hr_representative",
        ],
        "description": "Broad queries that should search all accessible collections",
    },
)

# ── Aggregate list ──────────────────────────────────────────────────────────

ALL_ROUTES: list[Route] = [
    finance_route,
    engineering_route,
    marketing_route,
    hr_general_route,
    cross_department_route,
]
