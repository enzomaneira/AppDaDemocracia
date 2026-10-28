import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Loading } from "./components/States";
import Account from "./pages/Account";
import Compare from "./pages/Compare";
import { Login, Register } from "./pages/Auth";
import Home from "./pages/Home";
import News from "./pages/News";
import Onboarding from "./pages/Onboarding";
import Search from "./pages/Search";
import { HowWeCalculate, NotFound, Privacy } from "./pages/Static";
import Vote from "./pages/Vote";
import Waitlist from "./pages/Waitlist";
import WaitlistAdmin from "./pages/WaitlistAdmin";

// O perfil carrega o Recharts; fica num chunk separado para o feed abrir rápido no celular.
const Politician = lazy(() => import("./pages/Politician"));

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="buscar" element={<Search />} />
        <Route
          path="politico/:slug"
          element={
            <Suspense fallback={<Loading />}>
              <Politician />
            </Suspense>
          }
        />
        <Route path="votacao/:id" element={<Vote />} />
        <Route path="noticias" element={<News />} />
        <Route path="comparar" element={<Compare />} />
        <Route path="lista" element={<Waitlist />} />
        <Route path="admin/lista" element={<WaitlistAdmin />} />
        <Route path="conta" element={<Account />} />
        <Route path="entrar" element={<Login />} />
        <Route path="cadastro" element={<Register />} />
        <Route path="comecar" element={<Onboarding />} />
        <Route path="como-calculamos" element={<HowWeCalculate />} />
        <Route path="privacidade" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
