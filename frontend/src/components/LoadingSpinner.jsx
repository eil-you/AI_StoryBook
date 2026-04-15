export default function LoadingSpinner({ message = "로딩 중..." }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
      <p className="text-gray-500 text-sm">{message}</p>
    </div>
  );
}
