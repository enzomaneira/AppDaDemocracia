import { Link } from "react-router-dom";

/** RNF06: metodologia pública, a mesma regra para todos os políticos. */
export function HowWeCalculate() {
  return (
    <article className="prose-sm flex max-w-2xl flex-col gap-4">
      <h1 className="text-2xl font-bold">Como calculamos</h1>
      <p className="muted">
        Todas as métricas usam dados oficiais da Câmara dos Deputados e do Senado Federal, sincronizados uma vez por
        dia às 03h (Brasília). A mesma regra vale para todos os parlamentares. O app não dá nota, não faz ranking e não
        classifica ninguém como “bom” ou “ruim”.
      </p>
      <Section title="Presença">
        <p>
          <strong>Presença = sessões deliberativas do Plenário com presença ÷ sessões deliberativas do período.</strong>
        </p>
        <p>
          Ausências justificadas (licença, missão oficial etc.) aparecem separadas e nunca são somadas às faltas, quando
          a fonte oficial informa a justificativa. Sessões não deliberativas e solenes não entram no cálculo.
        </p>
      </Section>
      <Section title="Votações nominais participadas">
        <p>
          Número de votações nominais do Plenário em que o parlamentar registrou voto (Sim, Não, Abstenção ou
          Obstrução). Votações simbólicas não têm registro individual e não entram na conta. Quem estava em exercício e
          não registrou voto aparece como “Ausente” naquela votação.
        </p>
      </Section>
      <Section title="Orientação do partido">
        <p>
          Mostramos a orientação de bancada publicada pela Câmara. Quando o partido integra uma federação ou bloco, vale a
          orientação do próprio partido; se ela não existir, a da federação.
        </p>
      </Section>
      <Section title="Proposições">
        <p>Proposições em que o parlamentar consta como autor, conforme o cadastro oficial de autoria.</p>
      </Section>
      <Section title="Gastos da cota parlamentar">
        <p>
          Soma dos valores líquidos da Cota para o Exercício da Atividade Parlamentar (CEAP, na Câmara; CEAPS, no
          Senado) no período. Gastos dentro do limite legal não indicam irregularidade.
        </p>
      </Section>
      <Section title="Período e média da casa">
        <p>
          O padrão é a legislatura atual, com filtro por ano. Toda métrica é exibida ao lado da média da mesma casa
          (Câmara ou Senado) no mesmo período.
        </p>
      </Section>
      <Section title="Notícias">
        <p>
          Uma notícia só é vinculada a um político quando o nome completo ou o nome parlamentar aparece no texto e o
          contexto confere (cargo, partido ou UF), para evitar homônimos. Exibimos apenas título, trecho curto, fonte e
          link para o veículo.
        </p>
      </Section>
    </article>
  );
}

export function Privacy() {
  return (
    <article className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-2xl font-bold">Privacidade</h1>
      <Section title="O que coletamos">
        <p>Somente nome, e-mail, estado (opcional) e a lista de parlamentares que você segue.</p>
      </Section>
      <Section title="Lista de seguidos">
        <p>
          Quem você segue pode revelar opinião política. Por isso essa lista é tratada como dado sensível: nunca é
          pública, não é compartilhada e só você tem acesso a ela.
        </p>
      </Section>
      <Section title="Seus direitos">
        <p>
          Em <Link to="/conta" className="text-marca underline">Conta</Link> você pode exportar todos os seus dados ou
          excluir a conta a qualquer momento.
        </p>
      </Section>
    </article>
  );
}

export function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <h1 className="text-2xl font-bold">Página não encontrada</h1>
      <Link to="/" className="btn-primary">
        Voltar ao início
      </Link>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card flex flex-col gap-2 text-sm leading-relaxed">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}
