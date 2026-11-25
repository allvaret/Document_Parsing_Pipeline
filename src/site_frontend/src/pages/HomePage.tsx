import { useEffect } from 'react'
import { SearchBox } from '../components/SearchBox'
import { Hero } from '../components/home/Hero'
import { CompanyGrid, HowItWorks, LatestReports } from '../components/home/HomeSections'
import { t } from '../i18n/pt'

export function HomePage() {
  useEffect(() => { document.title = 'RQ · Resumo qualitativo' }, [])
  return (
    <>
      <Hero />
      {/* Interior da maleta: veludo (CSS), cartões de papel por cima. */}
      <div className="velvet">
        <div className="relative mx-auto max-w-5xl space-y-14 px-4 pb-16 pt-20">
          <div id="busca" className="flex scroll-mt-8 justify-center">
            <SearchBox variant="hero" />
          </div>

          {/* Abas: só "Ações" existe. FIIs é backlog; nenhuma página falsa. */}
          <div>
            <div role="tablist" aria-label={t('home.tabsLabel')} className="flex gap-6 border-b border-paper/25">
              <button type="button" role="tab" id="tab-acoes" aria-selected="true" aria-controls="painel-acoes" className="tab tab-active">
                {t('home.tabStocks')}
              </button>
              <button type="button" role="tab" id="tab-fiis" aria-selected="false" disabled className="tab">
                {t('home.tabFiis')}
              </button>
            </div>
            <div role="tabpanel" id="painel-acoes" aria-labelledby="tab-acoes" className="space-y-14 pt-10">
              <LatestReports />
              <CompanyGrid />
            </div>
          </div>

          <HowItWorks />
        </div>
      </div>
    </>
  )
}
