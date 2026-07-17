import { createContext, useContext, useState, type ReactNode } from 'react';

interface AYContextType {
  currentAY: string;
  setCurrentAY: (ay: string) => void;
  // Aliases for backward compatibility with components
  ay: string;
  setAY: (ay: string) => void;
  ayParam: string;
}

const AYContext = createContext<AYContextType>({
  currentAY: '2026-27',
  setCurrentAY: () => {},
  ay: '2026-27',
  setAY: () => {},
  ayParam: '2026-27',
});

export function AYProvider({ children }: { children: ReactNode }) {
  const [currentAY, setCurrentAY] = useState('2026-27');
  return (
    <AYContext.Provider value={{ 
      currentAY, 
      setCurrentAY,
      ay: currentAY,
      setAY: setCurrentAY,
      ayParam: currentAY
    }}>
      {children}
    </AYContext.Provider>
  );
}

export function useAY() {
  return useContext(AYContext);
}
