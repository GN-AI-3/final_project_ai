from typing import Dict, Any, List

def analyze_nutrition(current: Dict[str, float], target: Dict[str, float]) -> Dict[str, float]:
    """영양소 결핍 분석"""
    deficiencies = {}
    for nutrient, target_amount in target.items():
        if nutrient in current:
            deficiency = target_amount - current[nutrient]
            if deficiency > 0:
                deficiencies[nutrient] = deficiency
    return deficiencies

def recommend_foods(deficiencies: Dict[str, float]) -> Dict[str, List[Dict[str, Any]]]:
    """부족한 영양소 기반 식품 추천"""
    recommendations = {}
    for nutrient, amount in deficiencies.items():
        recommendations[nutrient] = [
            {
                "name": f"{nutrient} rich food 1",
                "nutrition": {nutrient: amount * 1.5}
            },
            {
                "name": f"{nutrient} rich food 2",
                "nutrition": {nutrient: amount * 1.2}
            }
        ]
    return recommendations 