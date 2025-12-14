/**
 * Feature Modals
 * Gerencia os popups de informações das features
 */

// Verificar se já foi carregado
if (typeof window.featureData !== 'undefined') {
    console.log('feature-modals.js já carregado, ignorando redeclaração');
} else {

// Feature Data - Dados dos modals de features
window.featureData = {
    verified: {
        icon: 'fas fa-shield-alt',
        title: 'Conteúdo Verificado',
        text: 'Todos os arquivos em nossa plataforma passam por uma verificação de segurança e qualidade. Checamos a integridade dos arquivos, para garantir que você baixe apenas conteúdo funcional, seguro e livre de malware. Nossa equipe técnica revisa manualmente cada arquivo antes de disponibilizá-lo.'
    },
    updated: {
        icon: 'fas fa-rocket',
        title: 'Sempre Atualizado',
        text: 'Nossa plataforma é constantemente atualizada com novos conteúdos. Adicionamos regularmente novos arquivos ao nosso banco de dados para garantir que você tenha acesso a um acervo cada vez mais completo e diversificado.'
    },
    professional: {
        icon: 'fas fa-users',
        title: 'Feito para Profissionais',
        text: 'Nossa plataforma foi desenvolvida pensando nas necessidades de profissionais de informática. Organizamos o conteúdo de forma intuitiva, com filtros avançados, descrições detalhadas e informações técnicas precisas. Economize tempo em suas pesquisas e encontre exatamente o que precisa para seu trabalho.'
    },
    support: {
        icon: 'fas fa-headset',
        title: 'Suporte Dedicado',
        text: 'Nossa equipe de suporte está pronta para ajudá-lo. Se você não encontrar o arquivo que procura, tiver dúvidas sobre compatibilidade ou precisar de assistência técnica, entre em contato conosco. Respondemos rapidamente e fazemos o possível para atender suas solicitações específicas de recursos.'
    },
    // BIOS Features
    'bios-notebooks': {
        icon: 'fas fa-laptop',
        title: 'BIOS para Notebooks',
        text: 'Arquivos de BIOS específicos para notebooks de todas as principais marcas (Dell, HP, Lenovo, Acer, Asus, etc.). Essencial para reparos de placa-mãe.'
    },
    'bios-desktops': {
        icon: 'fas fa-desktop',
        title: 'BIOS para Desktops',
        text: 'BIOS para placas-mãe de computadores desktop de diversos fabricantes. Nossa coleção abrange desde placas antigas até modelos mais recentes, com suporte a múltiplos chipsets (Intel, AMD). Ideal para técnicos que trabalham com manutenção de PCs.'
    },
    'bios-monitores': {
        icon: 'fas fa-tv',
        title: 'BIOS para Monitores',
        text: 'Firmwares e BIOS para monitores LCD, LED e OLED das principais marcas como Samsung, LG, Dell, AOC e BenQ. Inclui arquivos para atualização de firmware, correção de problemas de imagem, ajuste de cores e configurações avançadas. Essencial para técnicos que trabalham com manutenção e reparo de monitores, permitindo resolver problemas de tela, botões, menus OSD e configurações de fábrica.'
    },
    'bios-embarcados': {
        icon: 'fas fa-microchip',
        title: 'BIOS para Sistemas Embarcados',
        text: 'Firmwares para sistemas embarcados, single-board computers (SBC), computadores industriais e dispositivos IoT. Inclui BIOS para Raspberry Pi, BeagleBone, sistemas POS e terminais especializados. Essencial para projetos de automação e dispositivos dedicados.'
    },
    // Esquemas Features
    'esquemas-placas': {
        icon: 'fas fa-memory',
        title: 'Esquemas de Placas-mãe',
        text: 'Esquemas elétricos completos (schematics e boardview) para placas-mãe de notebooks e desktops. Documentação técnica essencial para diagnóstico avançado de falhas, identificação de componentes danificados e reparos em nível de circuito. Compatível com softwares de análise de esquemas.'
    },
    'esquemas-carregamento': {
        icon: 'fas fa-battery-half',
        title: 'Circuitos de Carregamento',
        text: 'Esquemas detalhados dos circuitos de carregamento de bateria para notebooks e tablets. Inclui diagramas de tensão, pontos de medição e componentes críticos do sistema de alimentação. Fundamental para diagnóstico de problemas de carregamento e substituição de componentes do circuito de energia.'
    },
    'esquemas-conectores': {
        icon: 'fas fa-plug',
        title: 'Esquemas de Conectores',
        text: 'Pinouts e diagramas de conectores para diversos tipos de interfaces: LVDS (displays), USB-C, Thunderbolt, conectores de bateria, teclado, touchpad e outros. Inclui especificações elétricas, tensões e sinais de cada pino. Essencial para identificar conexões corretas durante reparos.'
    },
    'esquemas-fontes': {
        icon: 'fas fa-bolt',
        title: 'Circuitos de Fonte',
        text: 'Esquemas de fontes de alimentação ATX, SFX e fontes específicas de notebooks. Inclui diagramas de conversores DC-DC, reguladores de tensão e circuitos de proteção. Útil para diagnóstico de problemas de energia, reparo de fontes e identificação de componentes de potência.'
    },
    // Drivers Features
    'drivers-video': {
        icon: 'fas fa-tv',
        title: 'Drivers de Placas de Vídeo',
        text: 'Drivers para GPUs NVIDIA, AMD e Intel. Encontre o driver correto para sua placa de vídeo através do modelo ou Hardware ID, garantindo compatibilidade perfeita e melhor desempenho gráfico.'
    },
    'drivers-som': {
        icon: 'fas fa-volume-up',
        title: 'Drivers de Placas de Som',
        text: 'Drivers para chipsets de áudio Realtek, Creative, Conexant e outros fabricantes. Encontre o driver correto para resolver problemas de ausência de som, microfone não funcional e melhorar a qualidade de áudio.'
    },
    'drivers-rede': {
        icon: 'fas fa-wifi',
        title: 'Drivers de Rede/WiFi',
        text: 'Drivers para placas de rede ethernet (Intel, Realtek, Broadcom) e adaptadores WiFi (Qualcomm Atheros, MediaTek). Resolva problemas de conectividade e melhore a estabilidade da sua rede.'
    },
    'drivers-usb': {
        icon: 'fas fa-ellipsis-h',
        title: 'Outros Drivers',
        text: 'Drivers para diversos dispositivos: controladores USB, Bluetooth, chipsets, webcams, touchpads, card readers e outros periféricos. Encontre o driver correto para qualquer componente do seu sistema.'
    },
    // Softwares Features
    'softwares-diagnostico': {
        icon: 'fas fa-stethoscope',
        title: 'Ferramentas de Diagnóstico',
        text: 'Ferramentas profissionais para diagnóstico de hardware: HWiNFO, CPU-Z, GPU-Z, CrystalDiskInfo, MemTest86. Identifique problemas em processador, memória, disco, temperatura e estabilidade do sistema.'
    },
    'softwares-recuperacao': {
        icon: 'fas fa-redo',
        title: 'Softwares de Recuperação',
        text: 'Programas para recuperação de dados: Recuva, TestDisk, PhotoRec. Recupere arquivos deletados, partições perdidas e dados de discos danificados. Inclui ferramentas para clonagem e backup de discos.'
    },
    'softwares-limpeza': {
        icon: 'fas fa-broom',
        title: 'Ferramentas de Limpeza',
        text: 'Software para otimização e limpeza: CCleaner, BleachBit e outros utilitários. Desinstale aplicativos, limpe arquivos temporários, otimize o registro e melhore o desempenho geral do sistema.'
    },
    'softwares-benchmark': {
        icon: 'fas fa-tachometer-alt',
        title: 'Software de Benchmark',
        text: 'Ferramentas para teste de performance: Cinebench, Prime95, FurMark, CrystalDiskMark, Geekbench. Avalie o desempenho de CPU, GPU, RAM e armazenamento. Essencial para validar upgrades e comparar sistemas.'
    },
    // Impressoras Features
    'impressoras-drivers': {
        icon: 'fas fa-download',
        title: 'Drivers de Impressoras',
        text: 'Drivers oficiais e atualizados para impressoras de todas as marcas principais: HP, Canon, Epson, Brother, Samsung, Xerox. Inclui drivers para impressoras laser, jato de tinta, multifuncionais e plotters. Compatível com Windows, Linux e macOS.'
    },
    'impressoras-firmwares': {
        icon: 'fas fa-microchip',
        title: 'Firmwares para Impressoras',
        text: 'Arquivos de firmware para atualização e reparo de impressoras. Inclui firmwares para resolver problemas de travamento, erros de comunicação e incompatibilidades. Essencial para técnicos especializados em manutenção de impressoras.'
    },
    'impressoras-reset': {
        icon: 'fas fa-redo',
        title: 'Ferramentas de Reset',
        text: 'Software para reset de contadores de páginas, almofadas de tinta e chips. Programas como SSC Service Utility, WIC Reset e ferramentas específicas por fabricante. Essencial para manutenção preventiva e economia com cartuchos.'
    },
    'impressoras-manuais': {
        icon: 'fas fa-tools',
        title: 'Utilitários',
        text: 'Ferramentas e utilitários para manutenção de impressoras: programas de diagnóstico, ajuste de cabeçotes, limpeza de bicos, calibração de cores e outras utilidades. Inclui software de teste de páginas, ferramentas de alinhamento e programas de manutenção preventiva.'
    },
    // Cursos Features
    'cursos-video': {
        icon: 'fas fa-video',
        title: 'Vídeo Aulas',
        text: 'Cursos em vídeo sobre manutenção de computadores, redes, eletrônica e programação. Aulas práticas e teóricas ministradas por profissionais experientes. Inclui cursos de hardware, software, recuperação de dados e empreendedorismo na área técnica.'
    },
    'cursos-apostilas': {
        icon: 'fas fa-file-pdf',
        title: 'Apostilas e E-books',
        text: 'Material didático em PDF sobre diversos temas: hardware, redes, programação, eletrônica, segurança da informação. Apostilas técnicas detalhadas com exercícios práticos, diagramas e estudos de caso. Ideal para estudo autodidata.'
    },
    'cursos-certificados': {
        icon: 'fas fa-certificate',
        title: 'Cursos com Certificados',
        text: 'Cursos completos que oferecem certificado de conclusão reconhecido. Inclui trilhas de aprendizado estruturadas em manutenção de computadores, redes, Linux, segurança e gestão de TI. Certificações válidas para comprovar conhecimento técnico.'
    },
    'cursos-praticos': {
        icon: 'fas fa-book-open',
        title: 'Tutoriais em Vídeo',
        text: 'Tutoriais passo a passo em vídeo para resolver problemas comuns: substituição de componentes, instalação de drivers, configuração de sistemas. Acompanhe procedimentos reais de manutenção e reparo com explicações detalhadas.'
    }
};

// Função para inicializar os event listeners dos modals
function initFeatureModals() {
    const modal = document.getElementById('feature-modal');
    if (!modal) return; // Se não há modal na página, não faz nada

    const closeBtn = document.querySelector('.feature-modal-close');
    const featureItems = document.querySelectorAll('.feature-item[data-feature]');

    // Adiciona event listeners aos itens de feature
    featureItems.forEach(item => {
        item.addEventListener('click', function() {
            const feature = this.dataset.feature;
            const data = window.featureData[feature];

            if (data) {
                const iconElement = modal.querySelector('.feature-modal-icon');
                const titleElement = modal.querySelector('.feature-modal-title');
                const textElement = modal.querySelector('.feature-modal-text');

                if (iconElement && titleElement && textElement) {
                    iconElement.className = 'feature-modal-icon ' + data.icon;
                    titleElement.textContent = data.title;
                    textElement.textContent = data.text;
                    modal.style.display = 'block';
                    document.body.style.overflow = 'hidden';
                }
            }
        });
    });

    // Fecha o modal ao clicar no botão de fechar
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        });
    }

    // Fecha o modal ao clicar fora dele
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    });

    // Fecha o modal com a tecla ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    });
}

// Inicializa quando o DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFeatureModals);
} else {
    // DOM já está carregado (navegação entre páginas)
    initFeatureModals();
}

// Expõe a função globalmente para ser chamada pelo dynamic-loading
window.initFeatureModals = initFeatureModals;

} // Fim da verificação de carregamento
