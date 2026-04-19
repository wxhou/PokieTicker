## ADDED Requirements

### Requirement: Brand and product name

The product SHALL be branded as "涨讯" with appropriate visual identity.

#### Scenario: Brand displayed in header
- **WHEN** user opens the app
- **THEN** header SHALL display "涨讯" as product name
- **AND** subtext "A股事件驱动分析"

### Requirement: Chinese color convention (up=red, down=green)

The system SHALL use Chinese stock market color convention: red for price increases (涨), green for decreases (跌).

#### Scenario: Price increase displayed
- **WHEN** a stock price increases
- **THEN** the price/changes SHALL be displayed in red (#ff5252)
- **AND** up arrows/indicators SHALL be red

#### Scenario: Price decrease displayed
- **WHEN** a stock price decreases
- **THEN** the price/changes SHALL be displayed in green (#00e676)
- **AND** down arrows/indicators SHALL be green

### Requirement: Chinese typography

The system SHALL use PingFang SC as the primary font for Chinese text.

#### Scenario: Chinese text rendering
- **WHEN** app renders Chinese characters (news titles, analysis, UI labels)
- **THEN** font-family SHALL include "PingFang SC", "Microsoft YaHei", sans-serif

### Requirement: Loading states with skeleton screens

The system SHALL show skeleton placeholder content while data loads, using the existing shimmer animation.

#### Scenario: Data loading
- **WHEN** app fetches news/stock data
- **THEN** content area SHALL show skeleton placeholders matching the layout
- **AND** skeleton blocks SHALL have shimmer animation (existing CSS)
- **AND** NO spinner shall be shown

### Requirement: Last-viewed stock persistence

The system SHALL remember the user's last-viewed stock and restore it on next visit.

#### Scenario: Stock restored on reload
- **WHEN** user previously viewed a stock and returns to the app
- **THEN** system loads the last-viewed stock from localStorage
- **AND** chart and news panel show that stock

### Requirement: Legal disclaimer

The system SHALL display a prominent disclaimer on the prediction/analysis panel.

#### Scenario: Disclaimer visible
- **WHEN** user views the forecast/analysis panel
- **THEN** disclaimer text SHALL be visible at the bottom of the panel
- **AND** text SHALL state: "本工具仅供信息参考，不构成投资建议。用户需自行判断并承担投资风险。"
- **AND** disclaimer SHALL be non-dismissible

### Requirement: Chinese UI text

All user-facing text SHALL be in simplified Chinese.

#### Scenario: UI labels in Chinese
- **WHEN** app renders any UI element (buttons, labels, headers)
- **THEN** text SHALL be in simplified Chinese (e.g., "搜索" not "Search", "新闻" not "News")
- **AND** English-only technical terms (stock codes, model names) MAY remain in English
