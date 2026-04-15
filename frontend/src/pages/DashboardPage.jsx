import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteBook, listBooks } from "../api/books";
import Layout from "../components/Layout";
import LoadingSpinner from "../components/LoadingSpinner";

const STATUS_LABEL = {
  draft: { label: "초안", color: "bg-gray-100 text-gray-600" },
  published: { label: "출판됨", color: "bg-green-100 text-green-700" },
  finalized: { label: "완료", color: "bg-blue-100 text-blue-700" },
};

export default function DashboardPage() {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const fetchBooks = () => {
    setLoading(true);
    listBooks({ limit: 20, offset: 0 })
      .then((data) => setBooks(data.data ?? []))
      .catch(() => setError("책 목록을 불러오는데 실패했습니다."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBooks();
  }, []);

  const handleDelete = async (bookId) => {
    if (!window.confirm("정말 이 동화책을 삭제하시겠습니까?")) return;
    setDeletingId(bookId);
    try {
      await deleteBook(bookId);
      setBooks((prev) => prev.filter((b) => b.id !== bookId));
    } catch {
      setError("삭제에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">내 동화책</h1>
        <Link to="/generate" className="btn-primary">
          + 새 동화 만들기
        </Link>
      </div>

      {loading && <LoadingSpinner />}
      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && books.length === 0 && (
        <div className="card text-center py-16">
          <p className="text-gray-400 text-lg mb-4">아직 만든 동화책이 없어요</p>
          <Link to="/generate" className="btn-primary inline-block">
            첫 동화 만들기
          </Link>
        </div>
      )}

      {!loading && books.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {books.map((book) => {
            const status = STATUS_LABEL[book.status] ?? { label: book.status, color: "bg-gray-100 text-gray-600" };
            return (
              <div key={book.id} className="card hover:shadow-md transition-shadow">
                {book.cover_image_url ? (
                  <img
                    src={book.cover_image_url}
                    alt={book.title}
                    className="w-full h-40 object-cover rounded-lg mb-3"
                  />
                ) : (
                  <div className="w-full h-40 bg-gradient-to-br from-primary-100 to-purple-100 rounded-lg mb-3 flex items-center justify-center">
                    <span className="text-4xl">📖</span>
                  </div>
                )}
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-gray-900 line-clamp-2">{book.title}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${status.color}`}>
                    {status.label}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{book.content_summary}</p>
                <div className="mt-3 flex gap-2">
                  <Link
                    to={`/story/${book.id}/preview`}
                    className="btn-secondary text-xs py-1.5 flex-1 text-center"
                  >
                    미리보기
                  </Link>
                  {(book.status === "finalized" || book.status === "published" || book.status === "completed") && (
                    <Link
                      to={`/order/${book.id}`}
                      className="btn-primary text-xs py-1.5 flex-1 text-center"
                    >
                      주문하기
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(book.id)}
                    disabled={deletingId === book.id}
                    className="text-xs py-1.5 px-3 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 transition-colors"
                  >
                    {deletingId === book.id ? "..." : "삭제"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Layout>
  );
}
