import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AYProvider } from './contexts/AYContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ClientsPage from './pages/ClientsPage';
import FilingPage from './pages/FilingPage';
import ITRComputationPage from './pages/ITRComputationPage';
import AdvancedTaxPage from './pages/AdvancedTaxPage';

export default function App() {
  return (
    <AYProvider>
      <BrowserRouter>
        <Toaster position="top-right" />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/clients" element={<ClientsPage />} />
              <Route path="/filing" element={<FilingPage />} />
              <Route path="/filing/:clientId/:year" element={<ITRComputationPage />} />
              <Route path="/advanced-tax" element={<AdvancedTaxPage />} />
              <Route path="/advanced-tax/:calculatorId" element={<AdvancedTaxPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AYProvider>
  );
}
