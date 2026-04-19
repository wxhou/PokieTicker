## ADDED Requirements

### Requirement: Portfolio creation and management

Authenticated users SHALL be able to create, view, update, and delete stock portfolios.

#### Scenario: Create portfolio
- **WHEN** authenticated user creates a portfolio with name and up to 10 stock codes
- **THEN** system stores portfolio in `portfolios` table linked to user_id
- **AND** stores holdings in `portfolio_holdings` table

#### Scenario: Add stock to portfolio
- **WHEN** user adds a stock to existing portfolio
- **THEN** system adds entry to `portfolio_holdings` if count < 10
- **AND** returns updated portfolio

#### Scenario: Portfolio stock limit enforced
- **WHEN** user tries to add 11th stock
- **THEN** system returns 400 error with message "组合最多10只股票"

#### Scenario: Delete portfolio
- **WHEN** user deletes their own portfolio
- **THEN** system removes portfolio and all associated holdings

### Requirement: Portfolio view with daily summary

The system SHALL display a portfolio view showing all holdings with today's price change and event summary.

#### Scenario: Portfolio loads with holdings
- **WHEN** user views their portfolio
- **THEN** system returns all holdings with current prices from AKShare
- **AND** shows each stock's daily change (涨跌幅) with correct color (red=涨, green=跌)
- **AND** shows news count for each holding today

### Requirement: Single-stock view with event attribution

The system SHALL show a single-stock view with K-line, news events, and AI causal attribution.

#### Scenario: Stock detail loads
- **WHEN** user selects a stock from portfolio or search
- **THEN** system displays candlestick chart with news markers
- **AND** AI analysis showing today's key drivers
- **AND** historical similar patterns (v1.1 ML retraining deferred)
