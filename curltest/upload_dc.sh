curl -X POST http://127.0.0.1:8000/api/v1/documents/upload \
  -H "Authorization: Bearer rk_live_你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "bbd1c945-1d2b-49be-a13d-893e4921b352",
    "title": "退款政策",
    "content": "用户可在订单完成后 7 天内申请退款。特殊商品不支持无理由退款。退款会在 3 个工作日内到账。"
  }'
