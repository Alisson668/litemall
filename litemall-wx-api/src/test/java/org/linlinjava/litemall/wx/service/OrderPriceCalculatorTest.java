package org.linlinjava.litemall.wx.service;

import org.junit.Test;
import org.linlinjava.litemall.db.domain.LitemallCart;
import org.linlinjava.litemall.db.domain.LitemallGrouponRules;

import java.math.BigDecimal;
import java.util.Arrays;

import static org.junit.Assert.assertEquals;

public class OrderPriceCalculatorTest {
    private static final BigDecimal ZERO = new BigDecimal("0.00");

    @Test
    public void appliesGrouponDiscountOnlyToMatchingGoods() {
        LitemallCart grouponCart = cart(1, "100.00", 2);
        LitemallCart regularCart = cart(2, "50.00", 1);
        LitemallGrouponRules rules = new LitemallGrouponRules();
        rules.setGoodsId(1);

        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Arrays.asList(grouponCart, regularCart),
                rules,
                new BigDecimal("10.00"));

        assertPrice("230.00", result);
    }

    @Test
    public void calculatesFreightWhenGoodsPriceIsBelowLimit() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("80.00"),
                new BigDecimal("10.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("8.00", amount.getFreightPrice());
        assertPrice("78.00", amount.getOrderPrice());
    }

    @Test
    public void removesFreightWhenGoodsPriceReachesLimit() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("100.00"),
                new BigDecimal("20.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getFreightPrice());
        assertPrice("80.00", amount.getOrderPrice());
    }

    @Test
    public void clampsOrderPriceAtZero() {
        OrderPriceCalculator.Amount amount = OrderPriceCalculator.calculateAmount(
                new BigDecimal("10.00"),
                new BigDecimal("30.00"),
                new BigDecimal("88.00"),
                new BigDecimal("8.00"));

        assertPrice("0.00", amount.getOrderPrice());
    }

    @Test
    public void calculatesNonGrouponPrice() {
        BigDecimal result = OrderPriceCalculator.calculateGoodsPrice(
                Arrays.asList(cart(1, "19.90", 3)),
                null,
                ZERO);

        assertPrice("59.70", result);
    }

    private LitemallCart cart(int goodsId, String price, int number) {
        LitemallCart cart = new LitemallCart();
        cart.setGoodsId(goodsId);
        cart.setPrice(new BigDecimal(price));
        cart.setNumber((short) number);
        return cart;
    }

    private void assertPrice(String expected, BigDecimal actual) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual));
    }
}
