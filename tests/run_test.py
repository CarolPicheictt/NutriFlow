# tests/run_test.py
"""
Script de diagnóstico do pipeline NutriFlow.

Estrutura real do projeto:
    raiz/
    ├── scrap_do_pdf.py              ← WebDietParser
    ├── backend/app/core/shopping/
    │   └── calculator.py            ← ShoppingCalculator
    └── tests/
        ├── run_test.py              ← este arquivo
        └── Plano alimentar - Carolina Picheictt.pdf

Uso (execute sempre a partir da pasta raiz do projeto):
    cd Teste
    python tests/run_test.py "tests/Plano alimentar - Carolina Picheictt.pdf"
    python tests/run_test.py "tests/Plano alimentar - Carolina Picheictt.json"
"""

import sys
import json
from pathlib import Path

# ------------------------------------------------------------------
# Ajuste de PATH — resolve os imports independente de onde
# o script é chamado
# ------------------------------------------------------------------

# Raiz do projeto (pasta "Teste")
ROOT_DIR = Path(__file__).resolve().parent.parent

# Adiciona a raiz ao sys.path para encontrar scrap_do_pdf.py
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Adiciona backend/app ao sys.path para encontrar core/shopping/calculator.py
BACKEND_APP_DIR = ROOT_DIR / "backend" / "app"
if str(BACKEND_APP_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_APP_DIR))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def separador(titulo: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}")


# ------------------------------------------------------------------
# Etapa 1 — Parser
# ------------------------------------------------------------------

def testar_parser(caminho_pdf: Path) -> dict | None:
    """
    Testa se o WebDietParser consegue ler o PDF e
    retorna o DietPlan como dicionário.

    O parser está em scrap_do_pdf.py na raiz do projeto.
    """
    separador("ETAPA 1 — Parser WebDiet (scrap_do_pdf.py)")

    try:
        from scrap_do_pdf import WebDietParser
        print("✅ Módulo 'scrap_do_pdf' importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        print(f"   Esperado em: {ROOT_DIR / 'scrap_do_pdf.py'}")
        print(f"   Verifique se o arquivo existe nesse caminho")
        return None

    if not caminho_pdf.exists():
        print(f"❌ PDF não encontrado: {caminho_pdf}")
        print(f"   Caminho absoluto tentado: {caminho_pdf.resolve()}")
        return None

    try:
        parser = WebDietParser(caminho_pdf)
        diet_plan = parser.parse()
        print("✅ PDF processado com sucesso")
    except Exception as e:
        print(f"❌ Erro ao processar PDF: {e}")
        print(f"   Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None

    # Exibe resumo do que foi extraído
    print(f"\n📋 Dados extraídos:")
    print(f"   Paciente  : {diet_plan.patient.patient_name or '⚠️  não encontrado'}")
    print(f"   Aluno     : {diet_plan.patient.student_name or '⚠️  não encontrado'}")
    print(f"   Prescrito : {diet_plan.patient.prescribed_at or '⚠️  não encontrado'}")
    print(f"   Versão    : {diet_plan.patient.plan_version or '⚠️  não encontrado'}")
    print(f"   Refeições : {len(diet_plan.meals)}")
    print(f"   Compras   : {len(diet_plan.shopping_list)} itens brutos")
    print(f"   Receitas  : {len(diet_plan.recipes)}")

    if diet_plan.meals:
        print(f"\n🍽️  Refeições encontradas:")
        for meal in diet_plan.meals:
            nutrientes = "✅" if meal.nutrients else "⚠️  sem nutrientes"
            print(
                f"   {meal.time or '??:??'} — "
                f"{meal.name:<32} "
                f"{len(meal.items)} itens  {nutrientes}"
            )

            # Mostra os itens de cada refeição para diagnóstico
            for item in meal.items:
                qty = f"{item.quantity} {item.unit}" if item.quantity else item.raw_quantity or "?"
                print(f"            • {item.name:<30} {qty}")

    macros = diet_plan.nutritional_summary.macros
    if macros.calories_kcal:
        print(f"\n📊 Totais nutricionais:")
        print(f"   Calorias    : {macros.calories_kcal} kcal")
        print(f"   Proteínas   : {macros.proteins_g}g")
        print(f"   Carboidratos: {macros.carbs_g}g")
        print(f"   Lipídeos    : {macros.lipids_g}g")
    else:
        print(f"\n⚠️  Totais nutricionais não encontrados")

    # Salva o JSON gerado na pasta tests/
    output_path = ROOT_DIR / "tests" / "diet_plan_parsed.json"
    output_path.write_text(
        diet_plan.model_dump_json(indent=2),
        encoding="utf-8"
    )
    print(f"\n💾 JSON salvo em: {output_path}")

    return json.loads(diet_plan.model_dump_json())


# ------------------------------------------------------------------
# Etapa 2 — Calculator
# ------------------------------------------------------------------

def testar_calculator(diet_plan_dict: dict) -> None:
    """
    Testa o ShoppingCalculator com o DietPlan gerado pelo parser.

    O calculator está em backend/app/core/shopping/calculator.py.
    Requer correção do import interno do calculator.py
    conforme indicado abaixo.
    """
    separador("ETAPA 2 — Shopping Calculator")

    try:
        from scrap_do_pdf import DietPlan
        print("✅ DietPlan importado de scrap_do_pdf")
    except ImportError as e:
        print(f"❌ Não foi possível importar DietPlan: {e}")
        return

    try:
        from core.shopping.calculator import ShoppingCalculator
        print("✅ ShoppingCalculator importado de core.shopping.calculator")
    except ImportError as e:
        print(f"❌ Erro ao importar ShoppingCalculator: {e}")
        print(f"   Esperado em: {BACKEND_APP_DIR / 'core' / 'shopping' / 'calculator.py'}")
        print()
        print("   ⚠️  Verifique também se o import DENTRO do calculator.py")
        print("   foi ajustado de:")
        print("       from app.core.models.diet_plan import DietPlan, FoodItem")
        print("   para:")
        print("       from scrap_do_pdf import DietPlan, FoodItem")
        return

    try:
        diet_plan = DietPlan.model_validate(diet_plan_dict)
        print("✅ DietPlan reconstruído com sucesso")
    except Exception as e:
        print(f"❌ Erro ao reconstruir DietPlan: {e}")
        import traceback
        traceback.print_exc()
        return

    for days in [1, 7]:
        print(f"\n🛒 Lista de compras para {days} dia(s):")
        try:
            calc = ShoppingCalculator()
            items = calc.calculate(diet_plan, days=days)

            if not items:
                print("   ⚠️  Nenhum item gerado")
                print("   Causa provável: parser não extraiu FoodItems válidos")
                print("   Verifique a saída da Etapa 1 acima")
                continue

            print(f"   Total de itens únicos: {len(items)}")

            # Agrupa por categoria
            by_category: dict[str, list] = {}
            for item in items:
                by_category.setdefault(item.category, []).append(item)

            for category, cat_items in sorted(by_category.items()):
                print(f"\n   📦 {category.upper()}")
                for item in cat_items:
                    if item.unit_type.value == "free":
                        qty_str = "à vontade"
                    else:
                        qty_str = f"{item.total_quantity} {item.unit}"

                    suggestion = item.purchase_suggestion or ""
                    print(
                        f"      • {item.name:<35} "
                        f"{qty_str:<18} → {suggestion}"
                    )

        except Exception as e:
            print(f"   ❌ Erro no cálculo: {e}")
            import traceback
            traceback.print_exc()


# ------------------------------------------------------------------
# Modo JSON direto (pula o parser)
# ------------------------------------------------------------------

def testar_a_partir_de_json(caminho_json: Path) -> None:
    """
    Carrega um JSON já existente e testa apenas o calculator.
    Útil para iterar no calculator sem re-parsear o PDF.
    """
    separador("MODO JSON — Pulando o parser")

    if not caminho_json.exists():
        print(f"❌ JSON não encontrado: {caminho_json}")
        print(f"   Caminho absoluto: {caminho_json.resolve()}")
        return

    try:
        content = caminho_json.read_text(encoding="utf-8")
        diet_plan_dict = json.loads(content)
        print(f"✅ JSON carregado: {caminho_json}")
        testar_calculator(diet_plan_dict)
    except json.JSONDecodeError as e:
        print(f"❌ JSON inválido: {e}")


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

def main() -> None:
    separador("NUTRIFLOW — Diagnóstico do Pipeline")

    print(f"\n📁 Raiz do projeto  : {ROOT_DIR}")
    print(f"📁 Backend/app      : {BACKEND_APP_DIR}")
    print(f"📁 Script em        : {Path(__file__).resolve()}")

    if len(sys.argv) < 2:
        # Tenta localizar o PDF automaticamente na pasta tests/
        pdf_padrao = ROOT_DIR / "tests" / "Plano alimentar - Carolina Picheictt.pdf"
        json_padrao = ROOT_DIR / "tests" / "Plano alimentar - Carolina Picheictt.json"

        if pdf_padrao.exists():
            print(f"\n🔍 Nenhum argumento fornecido.")
            print(f"   PDF encontrado automaticamente: {pdf_padrao.name}")
            caminho = pdf_padrao
        elif json_padrao.exists():
            print(f"\n🔍 Nenhum argumento fornecido.")
            print(f"   JSON encontrado automaticamente: {json_padrao.name}")
            testar_a_partir_de_json(json_padrao)
            separador("FIM DO DIAGNÓSTICO")
            return
        else:
            print("\n  Uso:")
            print('    python tests/run_test.py "tests/Plano alimentar - Carolina Picheictt.pdf"')
            print('    python tests/run_test.py "tests/Plano alimentar - Carolina Picheictt.json"')
            sys.exit(1)
    else:
        caminho = Path(sys.argv[1])

    if caminho.suffix.lower() == ".json":
        testar_a_partir_de_json(caminho)
    elif caminho.suffix.lower() == ".pdf":
        diet_plan_dict = testar_parser(caminho)
        if diet_plan_dict:
            testar_calculator(diet_plan_dict)
    else:
        print(f"❌ Formato não suportado: {caminho.suffix}")
        sys.exit(1)

    separador("FIM DO DIAGNÓSTICO")


if __name__ == "__main__":
    main()