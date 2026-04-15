import { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("access_token");
    const email = localStorage.getItem("user_email");
    return token && email ? { email } : null;
  });

  const login = useCallback(async (email, password) => {
    const data = await apiLogin(email, password);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("user_email", email);
    setUser({ email });
  }, []);

  const register = useCallback(async (email, password) => {
    await apiRegister(email, password);
    await login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_email");
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
