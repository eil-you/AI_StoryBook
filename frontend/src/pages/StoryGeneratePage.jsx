import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { generateStory } from "../api/stories";
import Layout from "../components/Layout";

const GENRES      = ["모험", "판타지", "일상", "우정", "가족", "자연"];
const BACKGROUNDS = ["숲속", "우주", "바닷속", "마을", "학교", "마법의 세계"];
const EDUCATIONS  = ["용기", "친절", "우정", "정직", "협동", "창의력"];
const BOOK_SPEC_UID = "SQUAREBOOK_HC";

function ageLabel(age) {
  if (age <= 3)  return "유아 (1-3세)";
  if (age <= 6)  return "유치원 (4-6세)";
  if (age <= 9)  return "초등 저학년 (7-9세)";
  if (age <= 13) return "초등 고학년 (10-13세)";
  return "청소년 (14세+)";
}

function ChipSelect({ options, value, onChange, placeholder }) {
  return (
    <>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => onChange(o)}
            className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors
              ${value === o
                ? "bg-primary-600 text-white border-primary-600"
                : "bg-white text-gray-600 border-gray-300 hover:border-primary-400"
              }`}
          >
            {o}
          </button>
        ))}
      </div>
      <input
        type="text"
        value={options.includes(value) ? "" : value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field mt-2"
        placeholder={placeholder}
      />
    </>
  );
}

export default function StoryGeneratePage() {
  const navigate = useNavigate();
  const [step, setStep]       = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const [form, setForm] = useState({
    character_name: "",
    character_age:  5,
    genre:          "",
    background:     "",
    education:      "",
    book_spec_uid:  BOOK_SPEC_UID,
  });

  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const canNext = () => {
    if (step === 1) return form.character_name.trim() && form.character_age >= 1;
    if (step === 2) return form.genre && form.background;
    if (step === 3) return !!form.education;
    return true;
  };

  const handleGenerate = async () => {
    setError("");
    setLoading(true);
    try {
      const result = await generateStory(form);
      navigate(`/story/${result.book_id}/preview`, {
        state: { storyData: result.data },
      });
    } catch (err) {
      setError(err.response?.data?.detail || "스토리 생성에 실패했습니다.");
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold">동화 만들기</h1>
          {/* Step indicator */}
          <div className="flex items-center gap-2 mt-3">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold
                    ${step === s
                      ? "bg-primary-600 text-white"
                      : step > s
                        ? "bg-primary-200 text-primary-700"
                        : "bg-gray-200 text-gray-500"
                    }`}
                >
                  {step > s ? "✓" : s}
                </div>
                {s < 3 && (
                  <div className={`w-12 h-0.5 ${step > s ? "bg-primary-300" : "bg-gray-200"}`} />
                )}
              </div>
            ))}
            <span className="text-sm text-gray-500 ml-2">
              {step === 1 ? "주인공 설정" : step === 2 ? "이야기 배경" : "교육 가치"}
            </span>
          </div>
        </div>

        {/* Form card */}
        <div className="card">

          {/* Step 1 — 주인공 */}
          {step === 1 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">주인공을 소개해주세요</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">주인공 이름</label>
                <input
                  type="text"
                  value={form.character_name}
                  onChange={(e) => update("character_name", e.target.value)}
                  className="input-field"
                  placeholder="예: 민준, 지은, 하늘이..."
                  maxLength={50}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  주인공 나이:{" "}
                  <span className="text-primary-600 font-bold">{form.character_age}세</span>
                  <span className="text-xs text-gray-400 ml-2">({ageLabel(form.character_age)})</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={20}
                  value={form.character_age}
                  onChange={(e) => {
                    update("character_age", Number(e.target.value));
                  }}
                  className="w-full accent-primary-600"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>1세 (유아)</span>
                  <span>10세 (초등)</span>
                  <span>20세 (청소년)</span>
                </div>
                {/* 나이별 수준 안내 */}
                <div className="mt-2 px-3 py-2 bg-primary-50 rounded-lg text-xs text-primary-700">
                  {form.character_age <= 3  && "🍼 아주 짧고 단순한 문장, 반복되는 패턴으로 생성됩니다."}
                  {form.character_age >= 4  && form.character_age <= 6  && "🌸 쉬운 단어와 부드러운 이야기로 생성됩니다."}
                  {form.character_age >= 7  && form.character_age <= 9  && "📚 적당한 문장 길이와 가벼운 모험으로 생성됩니다."}
                  {form.character_age >= 10 && form.character_age <= 13 && "🌟 풍부한 표현과 캐릭터 성장이 담긴 이야기로 생성됩니다."}
                  {form.character_age >= 14 && "✨ 복잡한 감정과 깊이 있는 주제로 생성됩니다."}
                </div>
              </div>
            </div>
          )}

          {/* Step 2 — 배경 */}
          {step === 2 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">이야기의 배경을 선택해주세요</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">장르</label>
                <ChipSelect
                  options={GENRES}
                  value={form.genre}
                  onChange={(v) => update("genre", v)}
                  placeholder="직접 입력..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">배경/장소</label>
                <ChipSelect
                  options={BACKGROUNDS}
                  value={form.background}
                  onChange={(v) => update("background", v)}
                  placeholder="직접 입력..."
                />
              </div>
            </div>
          )}

          {/* Step 3 — 교육 가치 + 결과 */}
          {step === 3 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">어떤 가치를 가르쳐 주고 싶으신가요?</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">교육적 가치</label>
                <ChipSelect
                  options={EDUCATIONS}
                  value={form.education}
                  onChange={(v) => update("education", v)}
                  placeholder="직접 입력..."
                />
              </div>

              {/* 요약 */}
              <div className="bg-gray-50 rounded-xl p-4 text-sm text-gray-600 space-y-1">
                <p className="font-semibold text-gray-700 mb-2">생성 요약</p>
                <p>주인공: <strong>{form.character_name}</strong> ({form.character_age}세 · {ageLabel(form.character_age)})</p>
                <p>장르: <strong>{form.genre}</strong></p>
                <p>배경: <strong>{form.background}</strong></p>
                <p>교육 가치: <strong>{form.education}</strong></p>
              </div>

            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-red-500 text-sm bg-red-50 rounded-lg px-3 py-2 mt-4">{error}</p>
          )}

          {/* Navigation buttons */}
          <div className="flex gap-3 mt-6">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                disabled={loading}
                className="btn-secondary flex-1"
              >
                이전
              </button>
            )}

            {step < 3 ? (
              /* 다음 단계 버튼 */
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                disabled={!canNext()}
                className="btn-primary flex-1"
              >
                다음
              </button>
            ) : (
              /* Step 3 — 동화 만들기 */
              <button
                type="button"
                onClick={handleGenerate}
                disabled={loading || !canNext()}
                className="btn-primary flex-1"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    AI가 동화를 쓰고 있어요...
                  </span>
                ) : (
                  "동화 만들기 ✨"
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
