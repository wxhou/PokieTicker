## ADDED Requirements

### Requirement: Chinese keyword extraction with jieba

The system SHALL extract keywords from Chinese news headlines using jieba分词, replacing the existing English TICKER_KEYWORDS logic.

#### Scenario: Keywords extracted from news headline
- **WHEN** system processes a news headline in Chinese
- **THEN** jieba SHALL tokenize the text and extract nouns/verbs (removing stopwords)
- **AND** keywords with frequency >= 2 across recent articles SHALL be displayed as topic pills
- **AND** stopwords list SHALL include Chinese common words (的, 了, 在, 是, 我, 有, 和, etc.)

#### Scenario: Industry-specific financial terms preserved
- **WHEN** news contains financial terms: 茅台, 净利润, 涨跌幅, 北向资金, 主力
- **THEN** these terms SHALL NOT be filtered as stopwords
- **AND** they SHALL appear in the keyword extraction results

### Requirement: Sentence boundary detection for Chinese text

The AI conclusion/analysis text SHALL be split on Chinese sentence delimiters (。！？) instead of English periods.

#### Scenario: Conclusion split correctly
- **WHEN** AI returns a conclusion with multiple Chinese sentences
- **THEN** system SHALL split on 。！？ and display each as a bullet point
- **AND** empty sentences SHALL be filtered out
