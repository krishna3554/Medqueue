/* eslint-disable no-unused-vars -- JSX-only import flagged without the React plugin */
import { createRoot } from 'react-dom/client';
import { App } from './components/App';
import './styles.css';

createRoot(document.getElementById('root')).render(<App />);
