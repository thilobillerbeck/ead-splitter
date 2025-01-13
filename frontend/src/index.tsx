import { render } from 'preact';
import App from './App';
import 'the-new-css-reset/css/reset.css';

const root = document.getElementById('root');
if (root) {
  render(<App />, root);
}
