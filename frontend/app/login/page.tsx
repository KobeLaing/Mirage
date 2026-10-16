import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <div className="mx-auto mt-10 max-w-sm rounded-2xl bg-navy-800 p-6 shadow-2xl ring-1 ring-navy-700">
      <div className="mb-6 flex flex-col items-center text-center">
        {/* eslint-disable-next-line @next/next/no-img-element -- static local SVG */}
        <img src="/logo.svg" alt="" width={64} height={64} className="drop-shadow" />
        <h1 className="mt-3 text-2xl font-black text-ink">Sign in to Mirage</h1>
        <p className="mt-1 text-sm text-muted">AI or real? The community decides.</p>
      </div>
      <LoginForm />
    </div>
  );
}
