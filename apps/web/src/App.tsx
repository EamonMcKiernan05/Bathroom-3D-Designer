import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LandingPage } from './pages/Landing';
import { EditorPage } from './pages/Editor';
import { DesignsPage } from './pages/Designs';
import { DesignViewPage } from './pages/DesignView';
import { ExportPage } from './pages/ExportPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/editor" element={<EditorPage />} />
        <Route path="/designs" element={<DesignsPage />} />
        <Route path="/designs/:id" element={<DesignViewPage />} />
        <Route path="/designs/:id/bom" element={<ExportPage />} />
      </Routes>
    </BrowserRouter>
  );
}
