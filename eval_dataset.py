EVAL_DATASET = [

    # =========================
    # Account
    # =========================

    {
        "question":
            "忘记密码后多久必须完成重置？",

        "expected_document_id":
            "account_manual.txt",

        "expected_text":
            "密码重置链接有效期为30分钟。",

        "type":
            "direct"
    },

    {
        "question":
            "找回密码以后，多久之内要完成操作？",

        "expected_document_id":
            "account_manual.txt",

        "expected_text":
            "密码重置链接有效期为30分钟。",

        "type":
            "semantic"
    },

    # =========================
    # API
    # =========================

    {
        "question":
            "普通开发者一分钟最多调用多少次 API？",

        "expected_document_id":
            "api_manual.txt",

        "expected_text":
            "普通开发者账号每分钟最多可以发送60次 API 请求。",

        "type":
            "numeric"
    },

    {
        "question":
            "API Key 在哪里创建？",

        "expected_document_id":
            "api_manual.txt",

        "expected_text":
            "API Key 可以在开发者设置页面创建。",

        "type":
            "keyword"
    },

    {
        "question":
            "开发接口的访问凭证要去哪里生成？",

        "expected_document_id":
            "api_manual.txt",

        "expected_text":
            "API Key 可以在开发者设置页面创建。",

        "type":
            "semantic"
    },

    # =========================
    # Upload
    # =========================

    {
        "question":
            "哪些文件不能上传？",

        "expected_document_id":
            "upload_manual.txt",

        "expected_text":
            "目前不支持 EXE 和 ZIP 文件。",

        "type":
            "direct"
    },

    {
        "question":
            "ZIP 文件能上传吗？",

        "expected_document_id":
            "upload_manual.txt",

        "expected_text":
            "目前不支持 EXE 和 ZIP 文件。",

        "type":
            "keyword"
    },

    {
        "question":
            "可执行程序和压缩包能不能上传？",

        "expected_document_id":
            "upload_manual.txt",

        "expected_text":
            "目前不支持 EXE 和 ZIP 文件。",

        "type":
            "paraphrase"
    },

    # =========================
    # Refund
    # =========================

    {
        "question":
            "会员退款需要满足什么条件？",

        "expected_document_id":
            "refund_policy.txt",

        "expected_text":
            "购买会员后7天内",

        "type":
            "direct"
    },

    {
        "question":
            "购买会员几天之内可以申请退款？",

        "expected_document_id":
            "refund_policy.txt",

        "expected_text":
            "购买会员后7天内",

        "type":
            "numeric"
    },

    # =========================
    # Security
    # =========================

    {
        "question":
            "密码至少多少位？",

        "expected_document_id":
            "security_guide.txt",

        "expected_text":
            "密码长度应不少于8位。",

        "type":
            "numeric"
    },

    {
        "question":
            "设置密码时最低长度要求是多少？",

        "expected_document_id":
            "security_guide.txt",

        "expected_text":
            "密码长度应不少于8位。",

        "type":
            "semantic"
    },
]


NO_ANSWER_DATASET = [
    {
        "question":
            "支持微信支付吗?",

        "type":
            "no_answer"
    },

    {
        "question":
            "公司总部在哪里?",

        "type":
            "no_answer"
    },

    {
        "question":
            "支持支付宝提现吗?",

        "type":
            "no_answer"
    },

    {
        "question":
            "客服电话是多少?",

        "type":
            "no_answer"
    },

    {
        "question":
            "有手机 App 吗?",

        "type":
            "no_answer"
    }
]
