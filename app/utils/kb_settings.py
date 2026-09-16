from app.core.exceptions import AppError, ErrorCode


def validate_kb_settings(settings: dict) -> None:
    if not isinstance(settings, dict):
        raise AppError(
            ErrorCode.PARAM_ERROR,
            msg="settings 必须是 JSON 对象",
            context={"settings_type": type(settings).__name__},
        )

    synonyms = settings.get("synonyms")
    if synonyms is None:
        return
    if not isinstance(synonyms, list):
        raise AppError(
            ErrorCode.PARAM_ERROR,
            msg="settings.synonyms 必须是数组",
        )

    for index, group in enumerate(synonyms):
        if not isinstance(group, dict):
            raise AppError(
                ErrorCode.PARAM_ERROR,
                msg=f"synonyms[{index}] 必须是对象",
            )
        terms = group.get("terms")
        expand = group.get("expand")
        if not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t.strip() for t in terms):
            raise AppError(
                ErrorCode.PARAM_ERROR,
                msg=f"synonyms[{index}].terms 必须是非空字符串数组",
            )
        if not isinstance(expand, list) or not expand or not all(isinstance(t, str) and t.strip() for t in expand):
            raise AppError(
                ErrorCode.PARAM_ERROR,
                msg=f"synonyms[{index}].expand 必须是非空字符串数组",
            )
