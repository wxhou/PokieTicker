import { useState } from 'react';
import axios from 'axios';

interface Props {
  symbol: string;
}

export default function StoryPanel({ symbol }: Props) {
  const [story, setStory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function generateStory() {
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/analysis/story', { symbol });
      setStory(res.data.story);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '生成趋势故事失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="story-panel">
      <h2>趋势故事</h2>
      <button className="generate-story-btn" onClick={generateStory} disabled={loading || !symbol}>
        {loading ? '生成中...' : '生成故事'}
      </button>
      {error && <div className="error-message">{error}</div>}
      {story ? (
        <div className="story-content" dangerouslySetInnerHTML={{ __html: story }} />
      ) : (
        <div className="story-placeholder">
          点击上方按钮生成AI驱动的趋势故事
        </div>
      )}
    </div>
  );
}
