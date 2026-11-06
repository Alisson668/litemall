package org.linlinjava.litemall.wx.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.linlinjava.litemall.db.domain.LitemallCart;
import org.linlinjava.litemall.db.domain.LitemallGrouponRules;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;

@DisplayName("订单价格计算")
class OrderPriceCalculatorTest {
    private static final BigDecimal ZERO = new BigDecimal("0.00");

    @Test
    @DisplayName("团购优惠只作用于匹配商品")
    void appliesGrouponDiscountOnlyToMatchingGoods() {
        LitemallGrouponRules rules = grouponRules(1);

        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Arrays.asList(cart(1, "100.00", 2), cart(2, "50.00", 1)),
                rules,
                new BigDecimal("10.00"));

        assertPrice("230.00", result);
    }

    @Test
    @DisplayName("商品与团购规则不匹配时不减免")
    void doesNotDiscountDifferentGoods() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Collections.singletonList(cart(2, "100.00", 1)),
                grouponRules(1),
                new BigDecimal("10.00"));

        assertPrice("100.00", result);
    }

    @Test
    @DisplayName("团购规则商品 ID 为空时不减免")
    void doesNotDiscountWhenRuleGoodsIdMissing() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Collections.singletonList(cart(1, "100.00", 1)),
                grouponRules(null),
                new BigDecimal("10.00"));

        assertPrice("100.00", result);
    }

    @Test
    @DisplayName("商品 ID 为空时不发生团购匹配")
    void doesNotDiscountCartWithoutGoodsId() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Collections.singletonList(cart(null, "100.00", 1)),
                grouponRules(1),
                new BigDecimal("10.00"));

        assertPrice("100.00", result);
    }

    @Test
    @DisplayName("无团购规则时按原价计算")
    void calculatesWithoutGrouponRules() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Arrays.asList(cart(1, "19.90", 3), cart(2, "0.50", 2)),
                null,
                ZERO);

        assertPrice("60.70", result);
    }

    @Test
    @DisplayName("购物车为空时商品金额为零")
    void returnsZeroForEmptyCart() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Collections.emptyList(),
                null,
                ZERO);

        assertPrice("0.00", result);
    }

    @Test
    @DisplayName("低于运费门槛时收取运费")
    void calculatesFreightWhenGoodsPriceIsBelowLimit() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("80.00"),
                new BigDecimal("10.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertAll(
                () -> assertPrice("80.00", amount.getGoodsPrice()),
                () -> assertPrice("10.00", amount.getCouponPrice()),
                () -> assertPrice("8.00", amount.getFreightPrice()),
                () -> assertPrice("78.00", amount.getOrderPrice()));
    }

    @Test
    @DisplayName("恰好达到运费门槛时免运费")
    void removesFreightAtExactLimit() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("88.00"),
                ZERO,
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getFreightPrice());
        assertPrice("88.00", amount.getOrderPrice());
    }

    @Test
    @DisplayName("高于运费门槛时免运费")
    void removesFreightAboveLimit() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("100.00"),
                new BigDecimal("20.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getFreightPrice());
        assertPrice("80.00", amount.getOrderPrice());
    }

    @Test
    @DisplayName("优惠券超过订单金额时订单金额归零")
    void clampsOrderPriceAtZero() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("10.00"),
                new BigDecimal("30.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getOrderPrice());
    }

    @Test
    @DisplayName("优惠券恰好抵扣完订单金额时为零")
    void keepsExactZeroOrderPrice() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("10.00"),
                new BigDecimal("18.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getOrderPrice());
    }

    private LitemallCart cart(Integer goodsId, String price, int number) {
        LitemallCart cart = new LitemallCart();
        cart.setGoodsId(goodsId);
        cart.setPrice(new BigDecimal(price));
        cart.setNumber((short) number);
        return cart;
    }

    private LitemallGrouponRules grouponRules(Integer goodsId) {
        LitemallGrouponRules rules = new LitemallGrouponRules();
        rules.setGoodsId(goodsId);
        return rules;
    }

    private void assertPrice(String expected, BigDecimal actual) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual));
    }
}
