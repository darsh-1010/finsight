import { Provider } from 'react-redux';
import { BrowserRouter as Router } from 'react-router-dom';

import { GlobalWebSocket } from './components/GlobalWebSocket';
import { AuthProvider } from './context/AuthContext';
import { AlertProvider } from './context/AlertContext';
import ScrollToTop from './components/common/ScrollToTop';
import AppRoutes from './routes/AppRoutes';
import { store } from './store/store';

const App = () => (
  <Provider store={store}>
    <AuthProvider>
      <AlertProvider>
        <GlobalWebSocket />
        <Router>
          <ScrollToTop />
          <AppRoutes />
        </Router>
      </AlertProvider>
    </AuthProvider>
  </Provider>
);

export default App;