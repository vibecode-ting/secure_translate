import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Editor from './pages/Editor';
import Results from './pages/Results';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/editor/:documentId" element={<Editor />} />
        <Route path="/results/:documentId" element={<Results />} />
      </Routes>
    </Layout>
  );
}
