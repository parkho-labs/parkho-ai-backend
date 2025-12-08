from typing import Dict, Any, List


def build_error_response(error_message: str, error_code: str = "PROCESSING_ERROR") -> Dict[str, Any]:
    return {
        "success": False,
        "error": error_message,
        "error_code": error_code,
        "content": "",
        "metadata": {}
    }


def build_success_response(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": True,
        "content": content,
        "metadata": metadata,
        "error": None
    }


def build_multi_status_response(results: List[Dict[str, Any]]) -> int:
    if not results:
        return 400

    success_count = sum(1 for r in results if r.get("success"))

    if success_count == 0:
        return 400
    elif success_count == len(results):
        return 200
    else:
        return 207