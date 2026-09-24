"""
webdiet_parser.py

Parser estruturado para PDFs exportados pelo sistema WebDiet.
Converte o conteúdo do PDF em um modelo de dados canônico,
preparado para futura substituição por integração via API.

Dependências:
    pip install pdfplumber pydantic

Uso:
    parser = WebDietParser("dieta.pdf")
    diet_plan = parser.parse()
    print(diet_plan.model_dump_json(indent=2))
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

import pdfplumber
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DataSource(str, Enum):
    """
    Identifica a origem dos dados do plano alimentar.
    Permite que o modelo seja agnóstico à fonte,
    facilitando a migração futura para uma API.
    """
    WEBDIET_PDF = "webdiet_pdf"
    WEBDIET_API = "webdiet_api"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Modelos canônicos (Pydantic)
# ---------------------------------------------------------------------------

class FoodItem(BaseModel):
    """
    Representa um alimento individual dentro de uma refeição.

    Attributes:
        name: Nome do alimento conforme descrito no plano.
        quantity: Valor numérico da quantidade (ex: 100, 2, 0.5).
        unit: Unidade de medida (ex: 'g', 'ml', 'Unidade(s)', 'Colher(es)').
        raw_quantity: Texto original extraído do PDF, preservado para auditoria.
        substitution_for: Nome do alimento que este item pode substituir,
                          quando aplicável.
    """
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    raw_quantity: Optional[str] = None
    substitution_for: Optional[str] = None


class Meal(BaseModel):
    """
    Representa uma refeição do plano alimentar.

    Attributes:
        name: Nome da refeição (ex: 'Café da manhã', 'Almoço').
        time: Horário da refeição no formato 'HH:MM'.
        items: Lista de alimentos que compõem a refeição.
        substitutions: Alimentos alternativos indicados no plano.
        notes: Observações livres associadas à refeição.
        nutrients: Resumo nutricional da refeição, se disponível.
    """
    name: str
    time: Optional[str] = None
    items: list[FoodItem] = Field(default_factory=list)
    substitutions: list[FoodItem] = Field(default_factory=list)
    notes: Optional[str] = None
    nutrients: Optional[MealNutrients] = None


class MealNutrients(BaseModel):
    """
    Macronutrientes de uma refeição específica extraídos do
    relatório de nutrientes do WebDiet.

    Todos os valores são expressos em gramas (g),
    exceto calories (kcal).
    """
    proteins_g: Optional[float] = None
    lipids_g: Optional[float] = None
    carbs_g: Optional[float] = None
    calories_kcal: Optional[float] = None


class MacroNutrients(BaseModel):
    """
    Totais de macronutrientes do plano alimentar completo.

    Attributes:
        proteins_g: Proteínas totais em gramas.
        lipids_g: Lipídeos totais em gramas.
        carbs_g: Carboidratos totais em gramas.
        calories_kcal: Calorias totais em kcal.
    """
    proteins_g: Optional[float] = None
    lipids_g: Optional[float] = None
    carbs_g: Optional[float] = None
    calories_kcal: Optional[float] = None


class FattyAcids(BaseModel):
    """
    Perfil de ácidos graxos do plano alimentar, em gramas (g),
    exceto colesterol (mg).
    """
    monounsaturated_g: Optional[float] = None
    polyunsaturated_g: Optional[float] = None
    saturated_g: Optional[float] = None
    trans_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None


class Minerals(BaseModel):
    """
    Minerais presentes no plano alimentar.
    Valores em mg, exceto selênio (mcg).
    """
    calcium_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    phosphorus_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    sodium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    copper_mg: Optional[float] = None
    zinc_mg: Optional[float] = None
    selenium_mcg: Optional[float] = None


class Vitamins(BaseModel):
    """
    Vitaminas presentes no plano alimentar.
    Valores em mg, exceto vitaminas A (mcg), B9 (mcg),
    B12 (mcg), D (mcg).
    """
    vitamin_a_re_mcg: Optional[float] = None
    vitamin_a_rea_mcg: Optional[float] = None
    vitamin_b9_mcg: Optional[float] = None
    vitamin_b12_mcg: Optional[float] = None
    thiamine_mg: Optional[float] = None
    riboflavin_mg: Optional[float] = None
    pyridoxine_mg: Optional[float] = None
    niacin_mg: Optional[float] = None
    vitamin_c_mg: Optional[float] = None
    vitamin_d_mcg: Optional[float] = None
    vitamin_e_mg: Optional[float] = None


class NutritionalSummary(BaseModel):
    """
    Resumo nutricional completo do plano alimentar,
    incluindo macros, ácidos graxos, fibras, minerais e vitaminas.

    Attributes:
        macros: Totais de proteínas, lipídeos, carboidratos e calorias.
        fatty_acids: Perfil de ácidos graxos.
        fiber_g: Fibras totais em gramas.
        alcohol_g: Álcool total em gramas.
        minerals: Minerais do plano.
        vitamins: Vitaminas do plano.
    """
    macros: MacroNutrients = Field(default_factory=MacroNutrients)
    fatty_acids: FattyAcids = Field(default_factory=FattyAcids)
    fiber_g: Optional[float] = None
    alcohol_g: Optional[float] = None
    minerals: Minerals = Field(default_factory=Minerals)
    vitamins: Vitamins = Field(default_factory=Vitamins)


class RecipeIngredient(BaseModel):
    """
    Ingrediente de uma receita culinária presente no plano.

    Attributes:
        name: Nome do ingrediente.
        quantity: Texto original da quantidade (ex: '4 1/2 Copos americano duplos').
        amount_raw: Valor bruto original preservado para auditoria.
    """
    name: str
    quantity: Optional[str] = None
    amount_raw: Optional[str] = None


class Recipe(BaseModel):
    """
    Receita culinária incluída no plano alimentar.

    Attributes:
        name: Nome da receita.
        servings: Número de porções rendidas.
        ingredients: Lista de ingredientes com quantidades.
        instructions: Lista de passos do modo de preparo.
    """
    name: str
    servings: Optional[int] = None
    ingredients: list[RecipeIngredient] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)


class PatientInfo(BaseModel):
    """
    Informações do paciente e do documento extraídas do PDF.

    Attributes:
        patient_name: Nome do paciente conforme consta no documento.
        student_name: Nome do aluno/nutricionista responsável.
        prescribed_at: Data de prescrição do plano.
        plan_version: Versão ou identificador do plano (ex: 'Primeira +600 modificada').
    """
    patient_name: Optional[str] = None
    student_name: Optional[str] = None
    prescribed_at: Optional[date] = None
    plan_version: Optional[str] = None


class DietPlan(BaseModel):
    """
    Modelo canônico do plano alimentar completo.

    Este é o contrato central de dados do sistema.
    Independentemente da fonte (PDF, API futura, entrada manual),
    os dados são normalizados para esta estrutura.

    Attributes:
        source: Origem dos dados (ver DataSource).
        patient: Informações do paciente e do documento.
        meals: Lista de refeições do plano.
        nutritional_summary: Resumo nutricional completo.
        shopping_list: Lista de compras gerada pelo sistema.
        recipes: Receitas culinárias incluídas no plano.
    """
    source: DataSource = DataSource.WEBDIET_PDF
    patient: PatientInfo = Field(default_factory=PatientInfo)
    meals: list[Meal] = Field(default_factory=list)
    nutritional_summary: NutritionalSummary = Field(
        default_factory=NutritionalSummary
    )
    shopping_list: list[str] = Field(default_factory=list)
    recipes: list[Recipe] = Field(default_factory=list)


# Referência cruzada necessária para Meal usar MealNutrients
Meal.model_rebuild()


# ---------------------------------------------------------------------------
# Extrator de texto bruto
# ---------------------------------------------------------------------------

class PDFTextExtractor:
    """
    Responsável pela extração de texto bruto de um PDF usando pdfplumber.

    Isola a dependência com a biblioteca de leitura de PDF,
    facilitando troca futura por outra implementação (ex: PyMuPDF).
    """

    def __init__(self, pdf_path: str | Path) -> None:
        """
        Inicializa o extrator com o caminho do arquivo PDF.

        Args:
            pdf_path: Caminho absoluto ou relativo para o arquivo PDF.

        Raises:
            FileNotFoundError: Se o arquivo não existir no caminho fornecido.
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {self.pdf_path}")

    def extract_pages(self) -> list[str]:
        """
        Extrai o texto de cada página do PDF como uma lista de strings.

        Returns:
            Lista onde cada elemento é o texto de uma página do PDF.
            Páginas sem texto retornam string vazia.
        """
        pages: list[str] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return pages

    def extract_full_text(self) -> str:
        """
        Retorna o texto completo do PDF como uma única string,
        com separador de página entre cada página.

        Returns:
            Texto completo concatenado de todas as páginas.
        """
        return "\n\n--- PAGE BREAK ---\n\n".join(self.extract_pages())


# ---------------------------------------------------------------------------
# Parsers especializados por seção
# ---------------------------------------------------------------------------

class PatientInfoParser:
    """
    Extrai informações do paciente e metadados do documento.

    Padrões reconhecidos no cabeçalho do WebDiet:
        - 'Paciente Carolina Picheictt'
        - 'Prescrito em: 18/09/2026'
        - 'Aluno(a) Natalya Picheictt Carvalho Gomes'
        - 'Primeira +600 modificada'
    """

    # Padrões regex para extração dos campos do cabeçalho
    _RE_PATIENT = re.compile(r"Paciente\s+(.+?)(?:\s*\||\n)", re.IGNORECASE)
    _RE_PRESCRIBED = re.compile(r"Prescrito em:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
    _RE_STUDENT = re.compile(r"Aluno\(a\)\s+(.+?)(?:\n|$)", re.IGNORECASE)
    _RE_VERSION = re.compile(
        r"(Primeira|Segunda|Terceira|[\w\s]+)\s+\+?\d*\s*modificada",
        re.IGNORECASE
    )

    def parse(self, text: str) -> PatientInfo:
        """
        Analisa o texto completo do PDF e extrai os metadados do paciente.

        Args:
            text: Texto bruto extraído do PDF.

        Returns:
            Instância de PatientInfo com os campos encontrados preenchidos.
            Campos não encontrados permanecem None.
        """
        patient_name = self._extract(self._RE_PATIENT, text)
        prescribed_raw = self._extract(self._RE_PRESCRIBED, text)
        student_name = self._extract(self._RE_STUDENT, text)
        version = self._extract(self._RE_VERSION, text, group=0)

        prescribed_at: Optional[date] = None
        if prescribed_raw:
            try:
                day, month, year = prescribed_raw.split("/")
                prescribed_at = date(int(year), int(month), int(day))
            except ValueError:
                pass

        return PatientInfo(
            patient_name=patient_name,
            student_name=student_name,
            prescribed_at=prescribed_at,
            plan_version=version,
        )

    @staticmethod
    def _extract(
        pattern: re.Pattern,
        text: str,
        group: int = 1
    ) -> Optional[str]:
        """
        Aplica um padrão regex ao texto e retorna o grupo capturado,
        removendo espaços extras.

        Args:
            pattern: Padrão compilado a ser aplicado.
            text: Texto alvo da busca.
            group: Índice do grupo de captura desejado (padrão: 1).

        Returns:
            String capturada e limpa, ou None se não houver correspondência.
        """
        match = pattern.search(text)
        if match:
            return match.group(group).strip()
        return None


class MealParser:
    """
    Extrai as refeições e seus alimentos do texto do PDF WebDiet.

    O WebDiet estrutura cada refeição da seguinte forma:
        HH:MM - Nome da Refeição
        Nome do alimento    quantidade unidade (grammagem)
        ...
        • Opções de substituição para X:
        Nome substituto - quantidade unidade
        Observações:
        Texto livre

    Este parser identifica cada bloco de refeição e extrai
    os alimentos, substituições e observações associadas.
    """

    # Identifica o início de uma refeição: "07:00 - Café da manhã"
    _RE_MEAL_HEADER = re.compile(
        r"^(\d{2}:\d{2})\s*[-–]\s*(.+)$", re.MULTILINE
    )

    # Identifica linhas de alimento com quantidade e unidade
    # Exemplos:
    #   "Arroz branco cozido 150g"
    #   "Ovo de galinha 2 Unidade(s) (100g)"
    #   "Café coado (intenso) 0.5 Xícara(s) chá (100ml)"
    _RE_FOOD_ITEM = re.compile(
        r"^(?P<name>[A-ZÀ-Úa-zà-ú][\w\s\(\),./áéíóúâêîôûãõàèìòùç-]+?)"
        r"\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)"
        r"\s*"
        r"(?P<unit>[A-Za-zÀ-Úà-ú()./\s]+?)?"
        r"\s*(?:\([\d.,]+\w+\))?$",
        re.MULTILINE,
    )

    # Identifica bloco de substituições
    _RE_SUBSTITUTION_BLOCK = re.compile(
        r"Opções de substituição para (.+?):\s*\n(.+?)(?=\n\n|\n[A-Z]|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    # Identifica observações livres
    _RE_NOTES = re.compile(
        r"Observações:\s*\n(.+?)(?=\n\n|\n\d{2}:\d{2}|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    def parse(self, text: str) -> list[Meal]:
        """
        Divide o texto em blocos de refeição e processa cada um.

        Args:
            text: Texto bruto extraído do PDF.

        Returns:
            Lista de objetos Meal com alimentos, substituições e observações.
        """
        meal_blocks = self._split_into_meal_blocks(text)
        meals: list[Meal] = []

        for time_str, meal_name, block_text in meal_blocks:
            items = self._parse_food_items(block_text)
            substitutions = self._parse_substitutions(block_text)
            notes = self._parse_notes(block_text)

            meals.append(Meal(
                name=meal_name.strip(),
                time=time_str,
                items=items,
                substitutions=substitutions,
                notes=notes,
            ))

        return meals

    def _split_into_meal_blocks(
        self, text: str
    ) -> list[tuple[str, str, str]]:
        """
        Divide o texto completo em blocos individuais por refeição.

        Usa os cabeçalhos de horário como delimitadores de início de bloco.

        Args:
            text: Texto bruto do PDF.

        Returns:
            Lista de tuplas (horário, nome_refeição, texto_do_bloco).
        """
        headers = list(self._RE_MEAL_HEADER.finditer(text))
        blocks: list[tuple[str, str, str]] = []

        for i, match in enumerate(headers):
            start = match.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            block_text = text[start:end].strip()
            blocks.append((match.group(1), match.group(2), block_text))

        return blocks

    def _parse_food_items(self, block_text: str) -> list[FoodItem]:
        """
        Extrai os alimentos de um bloco de refeição.

        Filtra linhas que são cabeçalhos, observações ou substituições
        para isolar apenas os itens alimentares válidos.

        Args:
            block_text: Texto do bloco de uma única refeição.

        Returns:
            Lista de FoodItem extraídos do bloco.
        """
        items: list[FoodItem] = []
        skip_keywords = (
            "opções de substituição",
            "observações",
            "acesse o app",
            "página",
            "aluno",
        )

        for line in block_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(kw in line.lower() for kw in skip_keywords):
                continue

            food = self._parse_food_line(line)
            if food:
                items.append(food)

        return items

    def _parse_food_line(self, line: str) -> Optional[FoodItem]:
        """
        Tenta extrair nome, quantidade e unidade de uma linha de texto.

        Suporta formatos variados do WebDiet:
            - "Banana 1 Unidade(s) grande(s) (100g)"
            - "Arroz branco cozido 150g"
            - "Café coado (intenso) 0.5 Xícara(s) chá (100ml)"
            - "Salada com sal e vinagre À vontade"

        Args:
            line: Linha de texto a ser analisada.

        Returns:
            FoodItem se a linha contiver dados válidos, None caso contrário.
        """
        # Caso especial: "À vontade"
        if "à vontade" in line.lower():
            name = re.sub(r"[Àà] vontade", "", line, flags=re.IGNORECASE).strip()
            return FoodItem(
                name=name,
                raw_quantity="À vontade",
                unit="À vontade",
            )

        match = self._RE_FOOD_ITEM.match(line)
        if not match:
            return None

        name = match.group("name").strip()
        qty_raw = match.group("qty").replace(",", ".")
        unit = (match.group("unit") or "").strip() or None

        # Ignora linhas que parecem ser cabeçalhos ou metadados
        if len(name) < 3 or name.isdigit():
            return None

        try:
            quantity = float(qty_raw)
        except ValueError:
            quantity = None

        return FoodItem(
            name=name,
            quantity=quantity,
            unit=unit,
            raw_quantity=match.group(0).strip(),
        )

    def _parse_substitutions(self, block_text: str) -> list[FoodItem]:
        """
        Extrai os alimentos substitutos indicados no bloco de refeição.

        Formato esperado:
            • Opções de substituição para Ovo de galinha:
            Queijo branco - 2 Fatia(s) (60g)

        Args:
            block_text: Texto do bloco de uma única refeição.

        Returns:
            Lista de FoodItem marcados com o campo substitution_for preenchido.
        """
        substitutions: list[FoodItem] = []

        for match in self._RE_SUBSTITUTION_BLOCK.finditer(block_text):
            original_food = match.group(1).strip()
            sub_lines = match.group(2).strip().splitlines()

            for line in sub_lines:
                line = line.strip(" -•")
                if not line:
                    continue

                # Formato: "Queijo branco - 2 Fatia(s) (60g)"
                parts = line.split("-", 1)
                sub_name = parts[0].strip()
                sub_qty_raw = parts[1].strip() if len(parts) > 1 else None

                substitutions.append(FoodItem(
                    name=sub_name,
                    raw_quantity=sub_qty_raw,
                    substitution_for=original_food,
                ))

        return substitutions

    def _parse_notes(self, block_text: str) -> Optional[str]:
        """
        Extrai o texto de observações de um bloco de refeição.

        Args:
            block_text: Texto do bloco de uma única refeição.

        Returns:
            Texto das observações limpo, ou None se não houver.
        """
        match = self._RE_NOTES.search(block_text)
        if match:
            return match.group(1).strip()
        return None


class NutritionalReportParser:
    """
    Extrai o relatório de nutrientes do PDF WebDiet.

    O WebDiet gera uma tabela no seguinte formato:
        Refeição    Proteínas  Lipídeos  Carboidratos  Calorias
        Café da manhã  19.5g  14.3g  72.8g  490 Kcal
        ...
        Total das refeições  132.4g  88.4g  347.4g  2679 Kcal

    Seguido do detalhamento de vitaminas e minerais.
    """

    # Extrai linhas da tabela de nutrientes por refeição
    _RE_MEAL_ROW = re.compile(
        r"^(.+?)\s+"
        r"(\d+[.,]\d+)g\s+"
        r"(\d+[.,]\d+)g\s+"
        r"(\d+[.,]\d+)g\s+"
        r"(\d+)\s*Kcal$",
        re.MULTILINE | re.IGNORECASE,
    )

    # Extrai totais de micronutrientes
    _RE_FIBER = re.compile(r"Fibras\s+([\d.,]+)g", re.IGNORECASE)
    _RE_ALCOHOL = re.compile(r"Álcool\s+([\d.,]+)g", re.IGNORECASE)

    # Ácidos graxos
    _RE_MONO = re.compile(r"AG Monoinsat\.\s+([\d.,]+)g", re.IGNORECASE)
    _RE_POLY = re.compile(r"AG Poliinsat\.\s+([\d.,]+)g", re.IGNORECASE)
    _RE_SAT = re.compile(r"AG Saturada\s+([\d.,]+)g", re.IGNORECASE)
    _RE_TRANS = re.compile(r"AG Trans\s+([\d.,]+)g", re.IGNORECASE)
    _RE_CHOL = re.compile(r"Colesterol\s+([\d.,]+)mg", re.IGNORECASE)

    # Minerais
    _RE_CALCIUM = re.compile(r"Cálcio\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_MAGNESIUM = re.compile(r"Magnésio\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_PHOSPHORUS = re.compile(r"Fósforo\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_IRON = re.compile(r"Ferro\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_SODIUM = re.compile(r"Sódio\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_POTASSIUM = re.compile(r"Potássio\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_COPPER = re.compile(r"Cobre\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_ZINC = re.compile(r"Zinco\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_SELENIUM = re.compile(r"Selênio\s+([\d.,]+)mcg", re.IGNORECASE)

    # Vitaminas
    _RE_VIT_A_RE = re.compile(r"Vit\. A \(RE\)\s+([\d.,]+)mcg", re.IGNORECASE)
    _RE_VIT_A_REA = re.compile(r"Vit\. A \(REA\)\s+([\d.,]+)mcg", re.IGNORECASE)
    _RE_VIT_B9 = re.compile(r"Vit\. B9\s+([\d.,]+)mcg", re.IGNORECASE)
    _RE_VIT_B12 = re.compile(r"Vit\. B12\s+([\d.,]+)mcg", re.IGNORECASE)
    _RE_THIAMINE = re.compile(r"Tiamina\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_RIBOFLAVIN = re.compile(r"Riboflavina\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_PYRIDOXINE = re.compile(r"Piridoxina\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_NIACIN = re.compile(r"Niacina\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_VIT_C = re.compile(r"Vit\. C\s+([\d.,]+)mg", re.IGNORECASE)
    _RE_VIT_D = re.compile(r"Vit\. D\s+([\d.,]+)mcg", re.IGNORECASE)
    _RE_VIT_E = re.compile(r"Vitamina E\s+([\d.,]+)mg", re.IGNORECASE)

    def parse(self, text: str) -> tuple[NutritionalSummary, dict[str, MealNutrients]]:
        """
        Analisa o texto do PDF e retorna o resumo nutricional completo
        e um dicionário com os nutrientes por refeição.

        Args:
            text: Texto bruto extraído do PDF.

        Returns:
            Tupla contendo:
                - NutritionalSummary: resumo completo do plano.
                - dict[str, MealNutrients]: nutrientes indexados pelo nome
                  da refeição (chave em lowercase para comparação).
        """
        meal_nutrients = self._parse_meal_rows(text)
        summary = self._parse_summary(text, meal_nutrients)
        return summary, meal_nutrients

    def _parse_meal_rows(self, text: str) -> dict[str, MealNutrients]:
        """
        Extrai os nutrientes linha a linha da tabela de refeições.

        Args:
            text: Texto bruto do PDF.

        Returns:
            Dicionário com nome da refeição (lowercase) como chave
            e MealNutrients como valor.
        """
        result: dict[str, MealNutrients] = {}
        skip = {"total das refeições"}

        for match in self._RE_MEAL_ROW.finditer(text):
            meal_name = match.group(1).strip()
            if meal_name.lower() in skip:
                continue
            result[meal_name.lower()] = MealNutrients(
                proteins_g=self._to_float(match.group(2)),
                lipids_g=self._to_float(match.group(3)),
                carbs_g=self._to_float(match.group(4)),
                calories_kcal=self._to_float(match.group(5)),
            )

        return result

    def _parse_summary(
        self,
        text: str,
        meal_nutrients: dict[str, MealNutrients],
    ) -> NutritionalSummary:
        """
        Monta o NutritionalSummary com macros totais, ácidos graxos,
        fibras, minerais e vitaminas.

        Os macros totais são obtidos somando as refeições, pois o
        total explícito do PDF pode estar em formato variável.

        Args:
            text: Texto bruto do PDF.
            meal_nutrients: Nutrientes por refeição já extraídos.

        Returns:
            NutritionalSummary completo.
        """
        # Macros totais pela soma das refeições
        total_protein = sum(
            m.proteins_g or 0 for m in meal_nutrients.values()
        )
        total_lipids = sum(
            m.lipids_g or 0 for m in meal_nutrients.values()
        )
        total_carbs = sum(
            m.carbs_g or 0 for m in meal_nutrients.values()
        )
        total_calories = sum(
            m.calories_kcal or 0 for m in meal_nutrients.values()
        )

        return NutritionalSummary(
            macros=MacroNutrients(
                proteins_g=round(total_protein, 1),
                lipids_g=round(total_lipids, 1),
                carbs_g=round(total_carbs, 1),
                calories_kcal=round(total_calories, 1),
            ),
            fatty_acids=FattyAcids(
                monounsaturated_g=self._find(self._RE_MONO, text),
                polyunsaturated_g=self._find(self._RE_POLY, text),
                saturated_g=self._find(self._RE_SAT, text),
                trans_g=self._find(self._RE_TRANS, text),
                cholesterol_mg=self._find(self._RE_CHOL, text),
            ),
            fiber_g=self._find(self._RE_FIBER, text),
            alcohol_g=self._find(self._RE_ALCOHOL, text),
            minerals=Minerals(
                calcium_mg=self._find(self._RE_CALCIUM, text),
                magnesium_mg=self._find(self._RE_MAGNESIUM, text),
                phosphorus_mg=self._find(self._RE_PHOSPHORUS, text),
                iron_mg=self._find(self._RE_IRON, text),
                sodium_mg=self._find(self._RE_SODIUM, text),
                potassium_mg=self._find(self._RE_POTASSIUM, text),
                copper_mg=self._find(self._RE_COPPER, text),
                zinc_mg=self._find(self._RE_ZINC, text),
                selenium_mcg=self._find(self._RE_SELENIUM, text),
            ),
            vitamins=Vitamins(
                vitamin_a_re_mcg=self._find(self._RE_VIT_A_RE, text),
                vitamin_a_rea_mcg=self._find(self._RE_VIT_A_REA, text),
                vitamin_b9_mcg=self._find(self._RE_VIT_B9, text),
                vitamin_b12_mcg=self._find(self._RE_VIT_B12, text),
                thiamine_mg=self._find(self._RE_THIAMINE, text),
                riboflavin_mg=self._find(self._RE_RIBOFLAVIN, text),
                pyridoxine_mg=self._find(self._RE_PYRIDOXINE, text),
                niacin_mg=self._find(self._RE_NIACIN, text),
                vitamin_c_mg=self._find(self._RE_VIT_C, text),
                vitamin_d_mcg=self._find(self._RE_VIT_D, text),
                vitamin_e_mg=self._find(self._RE_VIT_E, text),
            ),
        )

    def _find(self, pattern: re.Pattern, text: str) -> Optional[float]:
        """
        Aplica um padrão ao texto e retorna o valor numérico capturado.

        Args:
            pattern: Padrão compilado com grupo de captura numérico.
            text: Texto alvo.

        Returns:
            Valor float extraído, ou None se não encontrado.
        """
        match = pattern.search(text)
        if match:
            return self._to_float(match.group(1))
        return None

    @staticmethod
    def _to_float(value: str) -> Optional[float]:
        """
        Converte string numérica (com vírgula ou ponto) para float.

        Args:
            value: String numérica, ex: '132,4' ou '132.4'.

        Returns:
            Valor float convertido, ou None em caso de falha.
        """
        try:
            return float(value.replace(",", "."))
        except (ValueError, AttributeError):
            return None


class ShoppingListParser:
    """
    Extrai a lista de compras do PDF WebDiet.

    O WebDiet apresenta a lista de compras como itens precedidos
    por um marcador circular (◯) em uma seção dedicada.
    """

    _RE_SECTION = re.compile(
        r"Lista de compras.+?(?=Acesse o app|Receita|$)",
        re.DOTALL | re.IGNORECASE,
    )
    _RE_ITEM = re.compile(r"◯\s+(.+)")

    def parse(self, text: str) -> list[str]:
        """
        Extrai os itens da lista de compras do texto do PDF.

        Args:
            text: Texto bruto extraído do PDF.

        Returns:
            Lista de strings com os nomes dos itens de compra.
            Retorna lista vazia se a seção não for encontrada.
        """
        section_match = self._RE_SECTION.search(text)
        if not section_match:
            return []

        section_text = section_match.group(0)
        return [
            match.group(1).strip()
            for match in self._RE_ITEM.finditer(section_text)
        ]


class RecipeParser:
    """
    Extrai receitas culinárias incluídas no plano alimentar WebDiet.

    Formato esperado:
        Nome da Receita
        Receita culinária
        Rendimento: N porção(ões).
        Ingredientes:
        Item - Quantidade
        ...
        Forma de preparo:
        1) Passo um
        2) Passo dois
        ...
    """

    _RE_RECIPE_BLOCK = re.compile(
        r"(.+?)\nReceita culinária\nRendimento:\s*(\d+)\s*porção.+?"
        r"Ingredientes:\n(.+?)Forma de preparo:\n(.+?)(?=\n\n[A-Z]|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    _RE_INSTRUCTION = re.compile(r"^\d+\)\s*(.+)$", re.MULTILINE)

    def parse(self, text: str) -> list[Recipe]:
        """
        Extrai todas as receitas culinárias do texto do PDF.

        Args:
            text: Texto bruto extraído do PDF.

        Returns:
            Lista de objetos Recipe com ingredientes e instruções.
        """
        recipes: list[Recipe] = []

        for match in self._RE_RECIPE_BLOCK.finditer(text):
            name = match.group(1).strip().splitlines()[-1].strip()
            servings = int(match.group(2))
            ingredients = self._parse_ingredients(match.group(3))
            instructions = self._parse_instructions(match.group(4))

            recipes.append(Recipe(
                name=name,
                servings=servings,
                ingredients=ingredients,
                instructions=instructions,
            ))

        return recipes

    def _parse_ingredients(self, text: str) -> list[RecipeIngredient]:
        """
        Extrai os ingredientes da seção de ingredientes da receita.

        Formato esperado por linha:
            "Nome do ingrediente - N Unidade(s) (XXg)"

        Args:
            text: Texto da seção de ingredientes.

        Returns:
            Lista de RecipeIngredient extraídos.
        """
        ingredients: list[RecipeIngredient] = []

        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(" - ", 1)
            name = parts[0].strip()
            quantity = parts[1].strip() if len(parts) > 1 else None

            if name:
                ingredients.append(RecipeIngredient(
                    name=name,
                    quantity=quantity,
                    amount_raw=line,
                ))

        return ingredients

    def _parse_instructions(self, text: str) -> list[str]:
        """
        Extrai os passos do modo de preparo da receita.

        Args:
            text: Texto da seção de modo de preparo.

        Returns:
            Lista de strings, cada uma representando um passo.
        """
        return [
            match.group(1).strip()
            for match in self._RE_INSTRUCTION.finditer(text)
        ]


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------

class WebDietParser:
    """
    Orquestrador principal do parser WebDiet.

    Coordena a extração de texto do PDF e delega para cada
    parser especializado, montando o DietPlan canônico final.

    Exemplo de uso:
        parser = WebDietParser("dieta.pdf")
        diet_plan = parser.parse()
        print(diet_plan.model_dump_json(indent=2))

    Para adaptar a uma API futura, basta implementar uma classe
    que produza um DietPlan diretamente, sem passar pelo PDF.
    """

    def __init__(self, pdf_path: str | Path) -> None:
        """
        Inicializa o parser com o caminho do arquivo PDF.

        Args:
            pdf_path: Caminho para o arquivo PDF exportado pelo WebDiet.
        """
        self._extractor = PDFTextExtractor(pdf_path)
        self._patient_parser = PatientInfoParser()
        self._meal_parser = MealParser()
        self._nutrition_parser = NutritionalReportParser()
        self._shopping_parser = ShoppingListParser()
        self._recipe_parser = RecipeParser()

    def parse(self) -> DietPlan:
        """
        Executa o pipeline completo de extração e retorna o DietPlan.

        Pipeline:
            1. Extrai texto bruto do PDF.
            2. Extrai metadados do paciente.
            3. Extrai refeições e alimentos.
            4. Extrai relatório nutricional e vincula às refeições.
            5. Extrai lista de compras.
            6. Extrai receitas culinárias.

        Returns:
            DietPlan com todos os dados estruturados e normalizados.
        """
        full_text = self._extractor.extract_full_text()

        patient = self._patient_parser.parse(full_text)
        meals = self._meal_parser.parse(full_text)
        nutritional_summary, meal_nutrients = self._nutrition_parser.parse(full_text)
        shopping_list = self._shopping_parser.parse(full_text)
        recipes = self._recipe_parser.parse(full_text)

        # Vincula os nutrientes a cada refeição pelo nome
        meals = self._bind_nutrients_to_meals(meals, meal_nutrients)

        return DietPlan(
            source=DataSource.WEBDIET_PDF,
            patient=patient,
            meals=meals,
            nutritional_summary=nutritional_summary,
            shopping_list=shopping_list,
            recipes=recipes,
        )

    @staticmethod
    def _bind_nutrients_to_meals(
        meals: list[Meal],
        meal_nutrients: dict[str, MealNutrients],
    ) -> list[Meal]:
        """
        Vincula os dados nutricionais do relatório a cada refeição.

        A correspondência é feita por similaridade de nome
        (comparação em lowercase, com verificação de substring).

        Args:
            meals: Lista de refeições extraídas.
            meal_nutrients: Dicionário de nutrientes por nome de refeição.

        Returns:
            Lista de refeições com o campo nutrients preenchido
            quando houver correspondência.
        """
        for meal in meals:
            meal_key = meal.name.lower()
            # Tentativa de correspondência exata
            if meal_key in meal_nutrients:
                meal.nutrients = meal_nutrients[meal_key]
                continue
            # Tentativa de correspondência por substring
            for key, nutrients in meal_nutrients.items():
                if key in meal_key or meal_key in key:
                    meal.nutrients = nutrients
                    break

        return meals


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python webdiet_parser.py <caminho_do_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"[WebDietParser] Processando: {pdf_path}\n")
    parser = WebDietParser(pdf_path)
    diet_plan = parser.parse()

    output = diet_plan.model_dump_json(indent=2)
    print(output)

    # Salva o resultado em JSON
    output_path = Path(pdf_path).with_suffix(".json")
    output_path.write_text(output, encoding="utf-8")
    print(f"\n[WebDietParser] Resultado salvo em: {output_path}")