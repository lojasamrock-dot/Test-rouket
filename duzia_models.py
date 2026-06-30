"""
Módulo separado para a classe EnsembleManual.

IMPORTANTE: Esta classe precisa viver em um arquivo .py próprio, importado
(não definido inline) pelo script principal do Streamlit. Isso é necessário
porque o Streamlit reexecuta o script principal inteiro a cada interação
(rerun). Se a classe fosse definida diretamente dentro do script principal,
cada rerun criaria um NOVO objeto de classe `EnsembleManual` em `__main__`.

O joblib/pickle salva instâncias referenciando a classe pelo seu módulo e
nome (`__main__.EnsembleManual`). Ao tentar serializar uma instância criada
em um rerun anterior usando a definição de classe do rerun atual, o pickle
encontra dois objetos de classe diferentes com o mesmo nome e lança:

    Can't pickle <class '__main__.EnsembleManual'>:
    it's not the same object as __main__.EnsembleManual

Como módulos importados (diferente do script principal) são carregados
apenas uma vez pelo Python e ficam em cache em sys.modules, a classe aqui
mantém uma identidade estável entre reruns, e o pickle/joblib funciona
normalmente para salvar e carregar o modelo do disco.
"""

import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class EnsembleManual:
    def __init__(self, rf, gbt):
        self.rf = rf
        self.gbt = gbt
        self.classes_ = rf.classes_

        try:
            self.n_features_in_ = rf.n_features_in_
        except AttributeError:
            try:
                self.n_features_in_ = gbt.n_features_in_
            except AttributeError:
                self.n_features_in_ = None

        self._modelo_tipo = "EnsembleManual"
        self._data_criacao = datetime.now().isoformat()
        self._melhor_accuracy = 0.0

    def predict_proba(self, X):
        try:
            p_rf = self.rf.predict_proba(X)
            p_gbt = self.gbt.predict_proba(X)
            return (p_rf + p_gbt) / 2.0, self.classes_
        except Exception as e:
            logger.error(f"❌ Erro no predict_proba: {e}")
            p_rf = self.rf.predict_proba(X)
            return p_rf, self.classes_

    def predict(self, X):
        try:
            proba, classes = self.predict_proba(X)
            return classes[np.argmax(proba, axis=1)]
        except Exception as e:
            logger.error(f"❌ Erro no predict: {e}")
            return self.rf.predict(X)
