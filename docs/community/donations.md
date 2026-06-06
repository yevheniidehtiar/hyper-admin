# Community Donation Options & Strategy

Research and recommendation for funding HyperAdmin's autonomous agentic workflow (Claude Max API subscription, approx. $100/mo).

> [!NOTE]
> This document analyzes donation platforms, tax/legal implications, and provides a turnkey configuration to kickstart community funding.

---

## Platform Comparison

| Platform | Fees | Target Audience | Primary Strengths | Major Weaknesses |
| :--- | :--- | :--- | :--- | :--- |
| **GitHub Sponsors** | **0%** | Developers & GitHub users | Native repo integration; zero fees; high trust. | Requires individual Stripe setup; no built-in tax-exempt status. |
| **Polar.sh** | **4%** + Stripe | Open Source Contributors | Merchant of Record (MoR) for global VAT; issue-based bounties. | Smaller user base; specialized for developers. |
| **Open Collective** | **5-10%** (via Host) | Teams & Projects | Full fiscal hosting; public ledger; handles legal/taxes. | High fees; complex claims process for payouts. |
| **Ko-fi** / **Buy Me a Coffee** | **0-5%** | Casual Creators | Extremely fast setup; easy one-off donations. | Not developer-focused; poor GitHub workflow integration. |

---

## Recommendation & Rationale

We recommend a hybrid approach to maximize funding with minimum administrative overhead:

1. **Primary Platform**: **GitHub Sponsors** for recurring monthly sponsorship.
   - *Why*: It has zero platform fees, resides directly inside the GitHub ecosystem, and offers the highest conversion rate for developers already viewing the repository.
2. **Bounty & Feature Funding**: **Polar.sh** for issue-based funding.
   - *Why*: Polar acts as the **Merchant of Record** (MoR—handles global sales tax compliance and VAT, saving us from global tax nightmares), allowing community members to fund specific features or bug fixes directly.

---

## Draft `FUNDING.yml`
Save this file in your repository under `.github/FUNDING.yml` to render sponsor buttons on GitHub:

```yaml
# .github/FUNDING.yml
github: yevheniidehtiar # GitHub Sponsors username
polar: yevheniidehtiar  # Polar.sh integration
custom: ["https://opencollective.com/hyper-admin"] # Fallback for corporate donors
```

---

## Proposed Sponsor Tiers

| Tier Name | Price | Target | Perks & Incentives |
| :--- | :--- | :--- | :--- |
| **Backer** | $5/mo | Individuals | Sponsor badge on profile; listed in `CONTRIBUTORS.md`. |
| **Active Supporter** | $15/mo | Power Users | Priority triage on bug reports; invite to private Discord channel. |
| **API Benefactor** | $50/mo | Heavy Users | Feeds 0.5x Claude Max agents. Logo on main `README.md`. |
| **Production Partner** | $100/mo | SMBs | Feeds 1.0x Claude Max agents. 1 hr/mo architecture consultation. |

---

## Legal, License, & Project Considerations

- **MIT License Obligations**: The MIT license allows sub-licensing, modification, and commercial use. Accepting donations does not conflict with MIT terms. Donations are voluntary contributions, not service agreements.
- **Tax Implications**: Since HyperAdmin is not a registered 501(c)(3) nonprofit, donations are treated as **personal taxable income** for the recipient under EU/US tax law.
- **Comparable Projects**:
  - *FastAPI* (uses GitHub Sponsors & Open Collective).
  - *Mitmproxy* (uses Open Collective to manage developer stipends).
  - *Ruff* (Astral funded via venture capital, but maintains GitHub Sponsors for community goodwill).
