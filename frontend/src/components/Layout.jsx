import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/dashboard" className="text-xl font-bold text-primary-700">
            AI StoryBook
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{user?.email}</span>
            <button onClick={handleLogout} className="btn-secondary text-sm py-1.5">
              로그아웃
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        {children}
      </main>
    </div>
  );
}
