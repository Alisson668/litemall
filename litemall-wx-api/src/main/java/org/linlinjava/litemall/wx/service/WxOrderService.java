package org.linlinjava.litemall.wx.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.binarywang.wxpay.bean.notify.WxPayNotifyResponse;
import com.github.binarywang.wxpay.bean.notify.WxPayOrderNotifyResult;
import com.github.binarywang.wxpay.bean.order.WxPayMpOrderResult;
import com.github.binarywang.wxpay.bean.order.WxPayMwebOrderResult;
import com.github.binarywang.wxpay.bean.request.WxPayUnifiedOrderRequest;
import com.github.binarywang.wxpay.bean.result.BaseWxPayResult;
import com.github.binarywang.wxpay.constant.WxPayConstants;
import com.github.binarywang.wxpay.exception.WxPayException;
import com.github.binarywang.wxpay.service.WxPayService;
import org.apache.commons.io.IOUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.linlinjava.litemall.core.express.ExpressService;
import org.linlinjava.litemall.core.express.dao.ExpressInfo;
import org.linlinjava.litemall.core.notify.NotifyService;
import org.linlinjava.litemall.core.notify.NotifyType;
import org.linlinjava.litemall.core.qcode.QCodeService;
import org.linlinjava.litemall.core.system.SystemConfig;
import org.linlinjava.litemall.core.task.TaskService;
import org.linlinjava.litemall.core.util.DateTimeUtil;
import org.linlinjava.litemall.core.util.JacksonUtil;
import org.linlinjava.litemall.core.util.ResponseUtil;
import org.linlinjava.litemall.db.domain.*;
import org.linlinjava.litemall.db.service.*;
import org.linlinjava.litemall.db.util.CouponUserConstant;
import org.linlinjava.litemall.db.util.GrouponConstant;
import org.linlinjava.litemall.db.util.OrderHandleOption;
import org.linlinjava.litemall.db.util.OrderUtil;
import org.linlinjava.litemall.core.util.IpUtil;
import org.linlinjava.litemall.wx.task.OrderUnpaidTask;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.linlinjava.litemall.wx.util.WxResponseCode.*;

/**
 * 订单服务
 *
 * <p>
 * 订单状态：
 * 101 订单生成，未支付；102，下单后未支付用户取消；103，下单后未支付超时系统自动取消
 * 201 支付完成，商家未发货；202，订单生产，已付款未发货，但是退款取消；
 * 301 商家发货，用户未确认；
 * 401 用户确认收货； 402 用户没有确认收货超过一定时间，系统自动确认收货；
 *
 * <p>
 * 用户操作：
 * 当101用户未付款时，此时用户可以进行的操作是取消订单，或者付款操作
 * 当201支付完成而商家未发货时，此时用户可以取消订单并申请退款
 * 当301商家已发货时，此时用户可以有确认收货的操作
 * 当401用户确认收货以后，此时用户可以进行的操作是删除订单，评价商品，申请售后，或者再次购买
 * 当402系统自动确认收货以后，此时用户可以删除订单，评价商品，申请售后，或者再次购买
 */
@Service
public class WxOrderService {
    private final Log logger = LogFactory.getLog(WxOrderService.class);
    private static final String EXPRESS_INFO = "expressInfo";
    private static final String GROUPON_LINK_ID = "grouponLinkId";
    private static final String ORDER_ID = "orderId";
    private static final String ORDER_UPDATE_EXPIRED = "更新数据已失效";
    private static final String ORDER_CANNOT_PAY = "订单不能支付";
    private static final BigDecimal ZERO_PRICE = BigDecimal.ZERO;

    @Autowired
    private LitemallUserService userService;
    @Autowired
    private LitemallOrderService orderService;
    @Autowired
    private LitemallOrderGoodsService orderGoodsService;
    @Autowired
    private LitemallAddressService addressService;
    @Autowired
    private LitemallCartService cartService;
    @Autowired
    private LitemallRegionService regionService;
    @Autowired
    private LitemallGoodsProductService productService;
    @Autowired
    private WxPayService wxPayService;
    @Autowired
    private NotifyService notifyService;
    @Autowired
    private LitemallGrouponRulesService grouponRulesService;
    @Autowired
    private LitemallGrouponService grouponService;
    @Autowired
    private QCodeService qCodeService;
    @Autowired
    private ExpressService expressService;
    @Autowired
    private LitemallCommentService commentService;
    @Autowired
    private LitemallCouponService couponService;
    @Autowired
    private LitemallCouponUserService couponUserService;
    @Autowired
    private CouponVerifyService couponVerifyService;
    @Autowired
    private TaskService taskService;
    @Autowired
    private LitemallAftersaleService aftersaleService;

    /**
     * 订单列表
     *
     * @param userId   用户ID
     * @param showType 订单信息：
     *                 0，全部订单；
     *                 1，待付款；
     *                 2，待发货；
     *                 3，待收货；
     *                 4，待评价。
     * @param page     分页页数
     * @param limit     分页大小
     * @return 订单列表
     */
    public Object list(Integer userId, Integer showType, Integer page, Integer limit, String sort, String order) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }

        List<Short> orderStatus = OrderUtil.orderStatus(showType);
        List<LitemallOrder> orderList = orderService.queryByOrderStatus(userId, orderStatus, page, limit, sort, order);

        List<Map<String, Object>> orderVoList = new ArrayList<>(orderList.size());
        for (LitemallOrder o : orderList) {
            Map<String, Object> orderVo = new HashMap<>();
            orderVo.put("id", o.getId());
            orderVo.put("orderSn", o.getOrderSn());
            orderVo.put("actualPrice", o.getActualPrice());
            orderVo.put("orderStatusText", OrderUtil.orderStatusText(o));
            orderVo.put("handleOption", OrderUtil.build(o));
            orderVo.put("aftersaleStatus", o.getAftersaleStatus());

            LitemallGroupon groupon = grouponService.queryByOrderId(o.getId());
            orderVo.put("isGroupin", groupon != null);

            List<LitemallOrderGoods> orderGoodsList = orderGoodsService.queryByOid(o.getId());
            List<Map<String, Object>> orderGoodsVoList = new ArrayList<>(orderGoodsList.size());
            for (LitemallOrderGoods orderGoods : orderGoodsList) {
                Map<String, Object> orderGoodsVo = new HashMap<>();
                orderGoodsVo.put("id", orderGoods.getId());
                orderGoodsVo.put("goodsName", orderGoods.getGoodsName());
                orderGoodsVo.put("number", orderGoods.getNumber());
                orderGoodsVo.put("picUrl", orderGoods.getPicUrl());
                orderGoodsVo.put("specifications", orderGoods.getSpecifications());
                orderGoodsVo.put("price",orderGoods.getPrice());
                orderGoodsVoList.add(orderGoodsVo);
            }
            orderVo.put("goodsList", orderGoodsVoList);

            orderVoList.add(orderVo);
        }

        return ResponseUtil.okList(orderVoList, orderList);
    }

    /**
     * 订单详情
     *
     * @param userId  用户ID
     * @param orderId 订单ID
     * @return 订单详情
     */
    public Object detail(Integer userId, Integer orderId) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }

        // 订单信息
        LitemallOrder order = orderService.findById(userId, orderId);
        if (null == order) {
            return ResponseUtil.fail(ORDER_UNKNOWN, "订单不存在");
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.fail(ORDER_INVALID, "不是当前用户的订单");
        }
        Map<String, Object> orderVo = new HashMap<>();
        orderVo.put("id", order.getId());
        orderVo.put("orderSn", order.getOrderSn());
        orderVo.put("message", order.getMessage());
        orderVo.put("addTime", order.getAddTime());
        orderVo.put("consignee", order.getConsignee());
        orderVo.put("mobile", order.getMobile());
        orderVo.put("address", order.getAddress());
        orderVo.put("goodsPrice", order.getGoodsPrice());
        orderVo.put("couponPrice", order.getCouponPrice());
        orderVo.put("freightPrice", order.getFreightPrice());
        orderVo.put("actualPrice", order.getActualPrice());
        orderVo.put("orderStatusText", OrderUtil.orderStatusText(order));
        orderVo.put("handleOption", OrderUtil.build(order));
        orderVo.put("aftersaleStatus", order.getAftersaleStatus());
        orderVo.put("expCode", order.getShipChannel());
        orderVo.put("expName", expressService.getVendorName(order.getShipChannel()));
        orderVo.put("expNo", order.getShipSn());

        List<LitemallOrderGoods> orderGoodsList = orderGoodsService.queryByOid(order.getId());

        Map<String, Object> result = new HashMap<>();
        result.put("orderInfo", orderVo);
        result.put("orderGoods", orderGoodsList);

        // 订单状态为已发货且物流信息不为空
        //"YTO", "800669400640887922"
        if (order.getOrderStatus().equals(OrderUtil.STATUS_SHIP)) {
            ExpressInfo ei = expressService.getExpressInfo(order.getShipChannel(), order.getShipSn());
            if(ei == null){
                result.put(EXPRESS_INFO, new ArrayList<>());
            }
            else {
                result.put(EXPRESS_INFO, ei);
            }
        }
        else{
            result.put(EXPRESS_INFO, new ArrayList<>());
        }

        return ResponseUtil.ok(result);

    }

    /**
     * 提交订单
     * <p>
     * 1. 创建订单表项和订单商品表项;
     * 2. 购物车清空;
     * 3. 优惠券设置已用;
     * 4. 商品货品库存减少;
     * 5. 如果是团购商品，则创建团购活动表项。
     *
     * @param userId 用户ID
     * @param body   订单信息，{ cartId：xxx, addressId: xxx, couponId: xxx, message: xxx, grouponRulesId: xxx,  grouponLinkId: xxx}
     * @return 提交订单操作结果
     */
    @Transactional
    public Object submit(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        if (body == null) {
            return ResponseUtil.badArgument();
        }
        try {
            return submitOrder(userId, SubmitOrderRequest.parse(body));
        }
        catch (OrderValidationException e) {
            return e.getResponse();
        }
    }

    private Object submitOrder(Integer userId, SubmitOrderRequest request) {
        if (!request.hasRequiredFields()) {
            throw new OrderValidationException(ResponseUtil.badArgument());
        }
        if (!request.hasValidValues()) {
            throw new OrderValidationException(ResponseUtil.badArgumentValue());
        }

        LitemallAddress address = addressService.query(userId, request.addressId);
        if (address == null) {
            throw new OrderValidationException(ResponseUtil.badArgument());
        }

        LitemallGrouponRules grouponRules = validateGroupon(
                userId, request.grouponRulesId, request.grouponLinkId);
        List<LitemallCart> carts = loadCheckedGoods(userId, request.cartId);
        if (carts.isEmpty()) {
            throw new OrderValidationException(ResponseUtil.badArgumentValue());
        }

        BigDecimal grouponPrice = grouponRules == null
                ? ZERO_PRICE : grouponRules.getDiscount();
        BigDecimal goodsPrice = OrderPriceCalculator.calculateGoodsPrice(
                carts, grouponRules, grouponPrice);
        CouponSelection coupon = calculateCoupon(userId, request, goodsPrice, carts);
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                goodsPrice,
                coupon.price,
                SystemConfig.getFreightLimit(),
                SystemConfig.getFreight());

        LitemallOrder order = createOrder(userId, request.message, address, amount, grouponPrice, grouponRules);
        if (orderService.add(order) == 0) {
            throw new OrderOperationException("创建订单失败");
        }

        saveOrderGoods(order, carts);
        removeCart(userId, request.cartId);
        deductStock(carts);
        markCouponUsed(order, coupon);
        LitemallGroupon groupon = createGroupon(userId, request, order.getId());
        boolean payed = completeZeroPriceOrder(order);
        return buildSubmitResult(order, payed, request.hasGroupon(), groupon);
    }

    private LitemallGrouponRules validateGroupon(Integer userId,
                                                  Integer rulesId,
                                                  Integer grouponLinkId) {
        if (!isPositive(rulesId)) {
            return null;
        }
        LitemallGrouponRules rules = grouponRulesService.findById(rulesId);
        if (rules == null) {
            throw new OrderValidationException(ResponseUtil.badArgument());
        }
        if (GrouponConstant.RULE_STATUS_DOWN_EXPIRE.equals(rules.getStatus())) {
            throw new OrderValidationException(
                    ResponseUtil.fail(GROUPON_EXPIRED, "团购已过期!"));
        }
        if (GrouponConstant.RULE_STATUS_DOWN_ADMIN.equals(rules.getStatus())) {
            throw new OrderValidationException(
                    ResponseUtil.fail(GROUPON_OFFLINE, "团购已下线!"));
        }
        validateGrouponParticipation(userId, rules, grouponLinkId);
        return rules;
    }

    private void validateGrouponParticipation(Integer userId,
                                              LitemallGrouponRules rules,
                                              Integer grouponLinkId) {
        if (!isPositive(grouponLinkId)) {
            return;
        }
        if (grouponService.countGroupon(grouponLinkId) >= rules.getDiscountMember() - 1) {
            throw new OrderValidationException(
                    ResponseUtil.fail(GROUPON_FULL, "团购活动人数已满!"));
        }
        if (grouponService.hasJoin(userId, grouponLinkId)) {
            throw new OrderValidationException(
                    ResponseUtil.fail(GROUPON_JOIN, "团购活动已经参加!"));
        }
        LitemallGroupon baseGroupon = grouponService.queryById(grouponLinkId);
        if (baseGroupon == null || userId.equals(baseGroupon.getCreatorUserId())) {
            throw new OrderValidationException(
                    ResponseUtil.fail(GROUPON_JOIN, "团购活动已经参加!"));
        }
    }

    private List<LitemallCart> loadCheckedGoods(Integer userId, Integer cartId) {
        if (cartId.equals(0)) {
            return cartService.queryByUidAndChecked(userId);
        }
        LitemallCart cart = cartService.findById(userId, cartId);
        if (cart == null) {
            throw new OrderValidationException(ResponseUtil.badArgumentValue());
        }
        List<LitemallCart> carts = new ArrayList<>(1);
        carts.add(cart);
        return carts;
    }

    private CouponSelection calculateCoupon(Integer userId,
                                            SubmitOrderRequest request,
                                            BigDecimal goodsPrice,
                                            List<LitemallCart> carts) {
        if (request.couponId == 0 || request.couponId == -1) {
            return CouponSelection.none();
        }
        LitemallCouponUser couponUser = resolveCouponUser(
                userId, request.couponId, request.userCouponId);
        LitemallCoupon coupon = couponVerifyService.checkCoupon(
                userId,
                request.couponId,
                couponUser.getId(),
                goodsPrice,
                carts);
        if (coupon == null) {
            throw new OrderValidationException(ResponseUtil.badArgumentValue());
        }
        return new CouponSelection(coupon.getDiscount(), couponUser);
    }

    private LitemallCouponUser resolveCouponUser(Integer userId,
                                                 Integer couponId,
                                                 Integer userCouponId) {
        LitemallCouponUser couponUser = userCouponId == null
                ? couponUserService.queryOne(userId, couponId)
                : couponUserService.findById(userCouponId);
        boolean belongsToUser = couponUser != null
                && userId.equals(couponUser.getUserId())
                && couponId.equals(couponUser.getCouponId());
        if (!belongsToUser) {
            throw new OrderValidationException(ResponseUtil.badArgumentValue());
        }
        return couponUser;
    }

    private LitemallOrder createOrder(Integer userId,
                                      String message,
                                      LitemallAddress address,
                                      OrderPriceCalculator.Amount amount,
                                      BigDecimal grouponPrice,
                                      LitemallGrouponRules grouponRules) {
        LitemallOrder order = new LitemallOrder();
        order.setUserId(userId);
        order.setOrderSn(orderService.generateOrderSn(userId));
        order.setOrderStatus(OrderUtil.STATUS_CREATE);
        order.setConsignee(address.getName());
        order.setMobile(address.getTel());
        order.setMessage(message);
        order.setAddress(buildDetailedAddress(address));
        order.setGoodsPrice(amount.getGoodsPrice());
        order.setFreightPrice(amount.getFreightPrice());
        order.setCouponPrice(amount.getCouponPrice());
        order.setIntegralPrice(ZERO_PRICE);
        order.setOrderPrice(amount.getOrderPrice());
        order.setActualPrice(amount.getOrderPrice());
        order.setGrouponPrice(grouponRules == null ? ZERO_PRICE : grouponPrice);
        return order;
    }

    private String buildDetailedAddress(LitemallAddress address) {
        return address.getProvince()
                + address.getCity()
                + address.getCounty()
                + " "
                + address.getAddressDetail();
    }

    private void saveOrderGoods(LitemallOrder order, List<LitemallCart> carts) {
        for (LitemallCart cart : carts) {
            LitemallOrderGoods orderGoods = new LitemallOrderGoods();
            orderGoods.setOrderId(order.getId());
            orderGoods.setGoodsId(cart.getGoodsId());
            orderGoods.setGoodsSn(cart.getGoodsSn());
            orderGoods.setProductId(cart.getProductId());
            orderGoods.setGoodsName(cart.getGoodsName());
            orderGoods.setPicUrl(cart.getPicUrl());
            orderGoods.setPrice(cart.getPrice());
            orderGoods.setNumber(cart.getNumber());
            orderGoods.setSpecifications(cart.getSpecifications());
            orderGoods.setAddTime(LocalDateTime.now());
            orderGoodsService.add(orderGoods);
        }
    }

    private void removeCart(Integer userId, Integer cartId) {
        if (cartId.equals(0)) {
            cartService.clearGoods(userId);
        }
        else {
            cartService.deleteById(cartId);
        }
    }

    private void deductStock(List<LitemallCart> carts) {
        for (LitemallCart cart : carts) {
            if (productService.reduceStock(cart.getProductId(), cart.getNumber()) == 0) {
                throw new OrderOperationException("商品货品库存减少失败");
            }
        }
    }

    private void markCouponUsed(LitemallOrder order, CouponSelection coupon) {
        if (coupon.userCoupon == null) {
            return;
        }
        coupon.userCoupon.setStatus(CouponUserConstant.STATUS_USED);
        coupon.userCoupon.setUsedTime(LocalDateTime.now());
        coupon.userCoupon.setOrderId(order.getId());
        if (couponUserService.update(coupon.userCoupon) == 0) {
            throw new OrderOperationException("更新优惠券状态失败");
        }
    }

    private LitemallGroupon createGroupon(Integer userId,
                                          SubmitOrderRequest request,
                                          Integer orderId) {
        if (!request.hasGroupon()) {
            return null;
        }
        LitemallGroupon groupon = new LitemallGroupon();
        groupon.setOrderId(orderId);
        groupon.setStatus(GrouponConstant.STATUS_NONE);
        groupon.setUserId(userId);
        groupon.setRulesId(request.grouponRulesId);

        if (isPositive(request.grouponLinkId)) {
            LitemallGroupon baseGroupon = grouponService.queryById(request.grouponLinkId);
            groupon.setCreatorUserId(baseGroupon.getCreatorUserId());
            groupon.setGrouponId(request.grouponLinkId);
            groupon.setShareUrl(baseGroupon.getShareUrl());
        }
        else {
            groupon.setCreatorUserId(userId);
            groupon.setCreatorUserTime(LocalDateTime.now());
            groupon.setGrouponId(0);
        }
        if (grouponService.createGroupon(groupon) == 0) {
            throw new OrderOperationException("创建团购记录失败");
        }
        return groupon;
    }

    private boolean completeZeroPriceOrder(LitemallOrder order) {
        if (order.getActualPrice().signum() != 0) {
            taskService.addTask(new OrderUnpaidTask(order.getId()));
            return false;
        }
        LitemallOrder paidOrder = new LitemallOrder();
        paidOrder.setId(order.getId());
        paidOrder.setOrderStatus(OrderUtil.STATUS_PAY);
        if (orderService.updateSelective(paidOrder) == 0) {
            throw new OrderOperationException(ORDER_UPDATE_EXPIRED);
        }
        if (!activateGrouponAfterPayment(order)) {
            throw new OrderOperationException(ORDER_UPDATE_EXPIRED);
        }
        notifyPaidOrder(order);
        return true;
    }

    private Object buildSubmitResult(LitemallOrder order,
                                     boolean payed,
                                     boolean hasGroupon,
                                     LitemallGroupon groupon) {
        Map<String, Object> data = new HashMap<>();
        data.put(ORDER_ID, order.getId());
        data.put("payed", payed);
        data.put(GROUPON_LINK_ID, grouponLinkId(hasGroupon, groupon));
        return ResponseUtil.ok(data);
    }

    private Integer grouponLinkId(boolean hasGroupon, LitemallGroupon groupon) {
        if (!hasGroupon || groupon == null) {
            return 0;
        }
        return groupon.getGrouponId() == 0 ? groupon.getId() : groupon.getGrouponId();
    }

    private static boolean isPositive(Integer value) {
        return value != null && value > 0;
    }

    private static final class SubmitOrderRequest {
        private final Integer cartId;
        private final Integer addressId;
        private final Integer couponId;
        private final Integer userCouponId;
        private final String message;
        private final Integer grouponRulesId;
        private final Integer grouponLinkId;

        private SubmitOrderRequest(Integer cartId,
                                   Integer addressId,
                                   Integer couponId,
                                   Integer userCouponId,
                                   String message,
                                   Integer grouponRulesId,
                                   Integer grouponLinkId) {
            this.cartId = cartId;
            this.addressId = addressId;
            this.couponId = couponId;
            this.userCouponId = userCouponId;
            this.message = message;
            this.grouponRulesId = grouponRulesId;
            this.grouponLinkId = grouponLinkId;
        }

        private static SubmitOrderRequest parse(String body) {
            Object parsed = JacksonUtil.toNode(body);
            if (!(parsed instanceof JsonNode) || !((JsonNode) parsed).isObject()) {
                throw new OrderValidationException(ResponseUtil.badArgumentValue());
            }
            JsonNode root = (JsonNode) parsed;
            return new SubmitOrderRequest(
                    parseInteger(root, "cartId"),
                    parseInteger(root, "addressId"),
                    parseInteger(root, "couponId"),
                    parseInteger(root, "userCouponId"),
                    parseString(root, "message"),
                    parseInteger(root, "grouponRulesId"),
                    parseInteger(root, GROUPON_LINK_ID));
        }

        private boolean hasRequiredFields() {
            return cartId != null && addressId != null && couponId != null;
        }

        private boolean hasValidValues() {
            return cartId >= 0
                    && addressId > 0
                    && couponId >= -1
                    && (userCouponId == null || userCouponId > 0)
                    && (grouponRulesId == null || grouponRulesId >= 0)
                    && (grouponLinkId == null || grouponLinkId >= 0);
        }

        private boolean hasGroupon() {
            return isPositive(grouponRulesId);
        }

        private static Integer parseInteger(JsonNode root, String field) {
            JsonNode leaf = root.get(field);
            if (leaf == null || leaf.isNull()) {
                return null;
            }
            if (!leaf.isIntegralNumber() || !leaf.canConvertToInt()) {
                throw new OrderValidationException(ResponseUtil.badArgumentValue());
            }
            return leaf.intValue();
        }

        private static String parseString(JsonNode root, String field) {
            JsonNode leaf = root.get(field);
            if (leaf == null || leaf.isNull()) {
                return null;
            }
            if (!leaf.isTextual()) {
                throw new OrderValidationException(ResponseUtil.badArgumentValue());
            }
            return leaf.textValue();
        }
    }

    private static final class CouponSelection {
        private final BigDecimal price;
        private final LitemallCouponUser userCoupon;

        private CouponSelection(BigDecimal price, LitemallCouponUser userCoupon) {
            this.price = price;
            this.userCoupon = userCoupon;
        }

        private static CouponSelection none() {
            return new CouponSelection(ZERO_PRICE, null);
        }
    }

    private static final class OrderValidationException extends RuntimeException {
        private static final long serialVersionUID = 1L;
        private final transient Object response;

        private OrderValidationException(Object response) {
            this.response = response;
        }

        private Object getResponse() {
            return response;
        }
    }

    private static final class OrderOperationException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        private OrderOperationException(String message) {
            super(message);
        }
    }

    /**
     * 取消订单
     * <p>
     * 1. 检测当前订单是否能够取消；
     * 2. 设置订单取消状态；
     * 3. 商品货品库存恢复；
     * 4. 返还优惠券；
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 取消订单操作结果
     */
    @Transactional
    public Object cancel(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgumentValue();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        // 检测是否能够取消
        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isCancel()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, "订单不能取消");
        }

        // 设置订单已取消状态
        order.setOrderStatus(OrderUtil.STATUS_CANCEL);
        order.setEndTime(LocalDateTime.now());
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            throw new OrderOperationException(ORDER_UPDATE_EXPIRED);
        }

        // 商品货品数量增加
        List<LitemallOrderGoods> orderGoodsList = orderGoodsService.queryByOid(orderId);
        for (LitemallOrderGoods orderGoods : orderGoodsList) {
            Integer productId = orderGoods.getProductId();
            Short number = orderGoods.getNumber();
            if (productService.addStock(productId, number) == 0) {
                throw new OrderOperationException("商品货品库存增加失败");
            }
        }

        // 返还优惠券
        releaseCoupon(orderId);

        return ResponseUtil.ok();
    }

    /**
     * 付款订单的预支付会话标识
     * <p>
     * 1. 检测当前订单是否能够付款
     * 2. 微信商户平台返回支付订单ID
     * 3. 设置订单付款状态
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 支付订单ID
     */
    @Transactional
    public Object prepay(Integer userId, String body, HttpServletRequest request) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgumentValue();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        // 检测是否能够取消
        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isPay()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, ORDER_CANNOT_PAY);
        }

        LitemallUser user = userService.findById(userId);
        String openid = user.getWeixinOpenid();
        if (openid == null) {
            return ResponseUtil.fail(AUTH_OPENID_UNACCESS, ORDER_CANNOT_PAY);
        }
        WxPayMpOrderResult result = null;
        try {
            WxPayUnifiedOrderRequest orderRequest = new WxPayUnifiedOrderRequest();
            orderRequest.setOutTradeNo(order.getOrderSn());
            orderRequest.setOpenid(openid);
            orderRequest.setBody("订单：" + order.getOrderSn());
            // 元转成分
            int fee = 0;
            BigDecimal actualPrice = order.getActualPrice();
            fee = actualPrice.multiply(new BigDecimal(100)).intValue();
            orderRequest.setTotalFee(fee);
            orderRequest.setSpbillCreateIp(IpUtil.getIpAddr(request));

            result = wxPayService.createOrder(orderRequest);
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseUtil.fail(ORDER_PAY_FAIL, ORDER_CANNOT_PAY);
        }

        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return ResponseUtil.updatedDateExpired();
        }
        return ResponseUtil.ok(result);
    }

    /**
     * 微信H5支付
     *
     * @param userId
     * @param body
     * @param request
     * @return
     */
    @Transactional
    public Object h5pay(Integer userId, String body, HttpServletRequest request) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgumentValue();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        // 检测是否能够取消
        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isPay()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, ORDER_CANNOT_PAY);
        }

        WxPayMwebOrderResult result = null;
        try {
            WxPayUnifiedOrderRequest orderRequest = new WxPayUnifiedOrderRequest();
            orderRequest.setOutTradeNo(order.getOrderSn());
            orderRequest.setTradeType("MWEB");
            orderRequest.setBody("订单：" + order.getOrderSn());
            // 元转成分
            int fee = 0;
            BigDecimal actualPrice = order.getActualPrice();
            fee = actualPrice.multiply(new BigDecimal(100)).intValue();
            orderRequest.setTotalFee(fee);
            orderRequest.setSpbillCreateIp(IpUtil.getIpAddr(request));

            result = wxPayService.createOrder(orderRequest);

        } catch (Exception e) {
            e.printStackTrace();
        }

        return ResponseUtil.ok(result);
    }

    /**
     * 微信付款成功或失败回调接口
     * <p>
     * 1. 检测当前订单是否是付款状态;
     * 2. 设置订单付款成功状态相关信息;
     * 3. 响应微信商户平台.
     *
     * @param request  请求内容
     * @param response 响应内容
     * @return 操作结果
     */
    @Transactional
    public Object payNotify(HttpServletRequest request, HttpServletResponse response) {
        String xmlResult = readPayNotify(request);
        if (xmlResult == null) {
            return WxPayNotifyResponse.fail("读取支付通知失败");
        }

        WxPayOrderNotifyResult result;
        try {
            result = parsePayNotify(xmlResult);
        }
        catch (WxPayException e) {
            logger.error("解析微信支付通知失败", e);
            return WxPayNotifyResponse.fail(e.getMessage());
        }

        logger.info("处理腾讯支付平台的订单支付");
        logger.info(result);

        String orderSn = result.getOutTradeNo();
        String payId = result.getTransactionId();
        String totalFee = BaseWxPayResult.fenToYuan(result.getTotalFee());
        LitemallOrder order = orderService.findBySn(orderSn);
        if (order == null) {
            return WxPayNotifyResponse.fail("订单不存在 sn=" + orderSn);
        }
        if (OrderUtil.hasPayed(order)) {
            return WxPayNotifyResponse.success("订单已经处理成功!");
        }
        if (!totalFee.equals(order.getActualPrice().toString())) {
            return WxPayNotifyResponse.fail(order.getOrderSn() + " : 支付金额不符合 totalFee=" + totalFee);
        }

        order.setPayId(payId);
        order.setPayTime(LocalDateTime.now());
        order.setOrderStatus(OrderUtil.STATUS_PAY);
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return WxPayNotifyResponse.fail(ORDER_UPDATE_EXPIRED);
        }
        if (!activateGrouponAfterPayment(order)) {
            return WxPayNotifyResponse.fail(ORDER_UPDATE_EXPIRED);
        }

        notifyPaidOrder(order);
        taskService.removeTask(new OrderUnpaidTask(order.getId()));
        return WxPayNotifyResponse.success("处理成功!");
    }

    private String readPayNotify(HttpServletRequest request) {
        try {
            return IOUtils.toString(request.getInputStream(), request.getCharacterEncoding());
        }
        catch (IOException e) {
            logger.error("读取微信支付通知失败", e);
            return null;
        }
    }

    private WxPayOrderNotifyResult parsePayNotify(String xmlResult) throws WxPayException {
        WxPayOrderNotifyResult result = wxPayService.parseOrderNotifyResult(xmlResult);
        if (result == null) {
            throw new WxPayException("微信支付通知内容为空");
        }
        if (!WxPayConstants.ResultCode.SUCCESS.equals(result.getResultCode())) {
            logger.error(xmlResult);
            throw new WxPayException("微信通知支付失败！");
        }
        if (!WxPayConstants.ResultCode.SUCCESS.equals(result.getReturnCode())) {
            logger.error(xmlResult);
            throw new WxPayException("微信通知支付失败！");
        }
        return result;
    }

    private boolean activateGrouponAfterPayment(LitemallOrder order) {
        LitemallGroupon groupon = grouponService.queryByOrderId(order.getId());
        if (groupon == null) {
            return true;
        }
        LitemallGrouponRules grouponRules = grouponRulesService.findById(groupon.getRulesId());
        if (grouponRules == null) {
            return false;
        }
        if (groupon.getGrouponId() == 0) {
            String url = qCodeService.createGrouponShareImage(
                    grouponRules.getGoodsName(), grouponRules.getPicUrl(), groupon);
            groupon.setShareUrl(url);
        }
        groupon.setStatus(GrouponConstant.STATUS_ON);
        if (grouponService.updateById(groupon) == 0) {
            return false;
        }
        completeGrouponIfFull(groupon, grouponRules);
        return true;
    }

    private void completeGrouponIfFull(LitemallGroupon groupon,
                                       LitemallGrouponRules grouponRules) {
        List<LitemallGroupon> grouponList = grouponService.queryJoinRecord(groupon.getGrouponId());
        if (groupon.getGrouponId() == 0
                || grouponList.size() < grouponRules.getDiscountMember() - 1) {
            return;
        }
        for (LitemallGroupon grouponActivity : grouponList) {
            grouponActivity.setStatus(GrouponConstant.STATUS_SUCCEED);
            grouponService.updateById(grouponActivity);
        }
        LitemallGroupon grouponSource = grouponService.queryById(groupon.getGrouponId());
        if (grouponSource != null) {
            grouponSource.setStatus(GrouponConstant.STATUS_SUCCEED);
            grouponService.updateById(grouponSource);
        }
    }

    private void notifyPaidOrder(LitemallOrder order) {
        notifyService.notifyMail("新订单通知", order.toString());
        notifyService.notifySmsTemplateSync(
                order.getMobile(),
                NotifyType.PAY_SUCCEED,
                new String[]{order.getOrderSn().substring(8, 14)});
    }

    /**
     * 订单申请退款
     * <p>
     * 1. 检测当前订单是否能够退款；
     * 2. 设置订单申请退款状态。
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 订单退款操作结果
     */
    public Object refund(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgument();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isRefund()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, "订单不能取消");
        }

        // 设置订单申请退款状态
        order.setOrderStatus(OrderUtil.STATUS_REFUND);
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return ResponseUtil.updatedDateExpired();
        }

        // 有用户申请退款，邮件通知运营人员
        notifyService.notifyMail("退款申请", order.toString());

        return ResponseUtil.ok();
    }

    /**
     * 确认收货
     * <p>
     * 1. 检测当前订单是否能够确认收货；
     * 2. 设置订单确认收货状态。
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 订单操作结果
     */
    public Object confirm(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgument();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isConfirm()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, "订单不能确认收货");
        }

        Short comments = orderGoodsService.getComments(orderId);
        order.setComments(comments);

        order.setOrderStatus(OrderUtil.STATUS_CONFIRM);
        order.setConfirmTime(LocalDateTime.now());
        if (orderService.updateWithOptimisticLocker(order) == 0) {
            return ResponseUtil.updatedDateExpired();
        }
        return ResponseUtil.ok();
    }

    /**
     * 删除订单
     * <p>
     * 1. 检测当前订单是否可以删除；
     * 2. 删除订单。
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 订单操作结果
     */
    public Object delete(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        Integer orderId = JacksonUtil.parseInteger(body, ORDER_ID);
        if (orderId == null) {
            return ResponseUtil.badArgument();
        }

        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgument();
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.badArgumentValue();
        }

        OrderHandleOption handleOption = OrderUtil.build(order);
        if (!handleOption.isDelete()) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, "订单不能删除");
        }

        // 订单order_status没有字段用于标识删除
        // 而是存在专门的delete字段表示是否删除
        orderService.deleteById(orderId);
        // 售后也同时删除
        aftersaleService.deleteByOrderId(userId, orderId);

        return ResponseUtil.ok();
    }

    /**
     * 待评价订单商品信息
     *
     * @param userId  用户ID
     * @param ogid 订单商品ID
     * @return 待评价订单商品信息
     */
    public Object goods(Integer userId, Integer ogid) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }
        LitemallOrderGoods orderGoods = orderGoodsService.findById(ogid);

        if (orderGoods != null) {
            Integer orderId = orderGoods.getOrderId();
            LitemallOrder order = orderService.findById(orderId);
            if (!order.getUserId().equals(userId)) {
                return ResponseUtil.badArgument();
            }
        }
        return ResponseUtil.ok(orderGoods);
    }

    /**
     * 评价订单商品
     * <p>
     * 确认商品收货或者系统自动确认商品收货后7天内可以评价，过期不能评价。
     *
     * @param userId 用户ID
     * @param body   订单信息，{ orderId：xxx }
     * @return 订单操作结果
     */
    public Object comment(Integer userId, String body) {
        if (userId == null) {
            return ResponseUtil.unlogin();
        }

        Integer orderGoodsId = JacksonUtil.parseInteger(body, "orderGoodsId");
        if (orderGoodsId == null) {
            return ResponseUtil.badArgument();
        }
        LitemallOrderGoods orderGoods = orderGoodsService.findById(orderGoodsId);
        if (orderGoods == null) {
            return ResponseUtil.badArgumentValue();
        }
        Integer orderId = orderGoods.getOrderId();
        LitemallOrder order = orderService.findById(userId, orderId);
        if (order == null) {
            return ResponseUtil.badArgumentValue();
        }
        if (!OrderUtil.isConfirmStatus(order) && !OrderUtil.isAutoConfirmStatus(order)) {
            return ResponseUtil.fail(ORDER_INVALID_OPERATION, "当前商品不能评价");
        }
        if (!order.getUserId().equals(userId)) {
            return ResponseUtil.fail(ORDER_INVALID, "当前商品不属于用户");
        }
        Integer commentId = orderGoods.getComment();
        if (commentId == -1) {
            return ResponseUtil.fail(ORDER_COMMENT_EXPIRED, "当前商品评价时间已经过期");
        }
        if (commentId != 0) {
            return ResponseUtil.fail(ORDER_COMMENTED, "订单商品已评价");
        }

        String content = JacksonUtil.parseString(body, "content");
        Integer star = JacksonUtil.parseInteger(body, "star");
        if (star == null || star < 0 || star > 5) {
            return ResponseUtil.badArgumentValue();
        }
        Boolean hasPicture = JacksonUtil.parseBoolean(body, "hasPicture");
        List<String> picUrls = JacksonUtil.parseStringList(body, "picUrls");
        if (hasPicture == null || !hasPicture) {
            picUrls = new ArrayList<>(0);
        }

        // 1. 创建评价
        LitemallComment comment = new LitemallComment();
        comment.setUserId(userId);
        comment.setType((byte) 0);
        comment.setValueId(orderGoods.getGoodsId());
        comment.setStar(star.shortValue());
        comment.setContent(content);
        comment.setHasPicture(hasPicture);
        comment.setPicUrls(picUrls.toArray(new String[]{}));
        commentService.save(comment);

        // 2. 更新订单商品的评价列表
        orderGoods.setComment(comment.getId());
        orderGoodsService.updateById(orderGoods);

        // 3. 更新订单中未评价的订单商品可评价数量
        Short commentCount = order.getComments();
        if (commentCount > 0) {
            commentCount--;
        }
        order.setComments(commentCount);
        orderService.updateWithOptimisticLocker(order);

        return ResponseUtil.ok();
    }

    /**
     * 取消订单/退款返还优惠券
     * <br/>
     * @param orderId
     * @return void
     * @author Tyson
     * @date 2020/6/8/0008 1:41
     */
    public void releaseCoupon(Integer orderId) {
        List<LitemallCouponUser> couponUsers = couponUserService.findByOid(orderId);
        for (LitemallCouponUser couponUser: couponUsers) {
            // 优惠券状态设置为可使用
            couponUser.setStatus(CouponUserConstant.STATUS_USABLE);
            couponUser.setUpdateTime(LocalDateTime.now());
            couponUserService.update(couponUser);
        }
    }
}
