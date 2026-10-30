package org.linlinjava.litemall.wx.service;

import org.linlinjava.litemall.db.domain.LitemallCart;
import org.linlinjava.litemall.db.domain.LitemallGrouponRules;

import java.math.BigDecimal;
import java.util.List;

/**
 * Pure price calculation used by order submission.
 */
final class OrderPriceCalculator {
    private static final BigDecimal ZERO = BigDecimal.ZERO;

    private OrderPriceCalculator() {
    }

    static BigDecimal calculateGoodsPrice(List<LitemallCart> carts,
                                          LitemallGrouponRules grouponRules,
                                          BigDecimal grouponPrice) {
        BigDecimal goodsPrice = ZERO;
        for (LitemallCart cart : carts) {
            BigDecimal itemPrice = cart.getPrice();
            if (isGrouponGoods(cart, grouponRules)) {
                itemPrice = itemPrice.subtract(grouponPrice);
            }
            goodsPrice = goodsPrice.add(
                    itemPrice.multiply(BigDecimal.valueOf(cart.getNumber())));
        }
        return goodsPrice;
    }

    static Amount calculateAmount(BigDecimal goodsPrice,
                                  BigDecimal couponPrice,
                                  BigDecimal freightLimit,
                                  BigDecimal freight) {
        BigDecimal actualFreight = goodsPrice.compareTo(freightLimit) < 0 ? freight : ZERO;
        BigDecimal orderPrice = goodsPrice
                .add(actualFreight)
                .subtract(couponPrice)
                .max(ZERO);
        return new Amount(goodsPrice, couponPrice, actualFreight, orderPrice);
    }

    private static boolean isGrouponGoods(LitemallCart cart, LitemallGrouponRules grouponRules) {
        return grouponRules != null
                && grouponRules.getGoodsId() != null
                && grouponRules.getGoodsId().equals(cart.getGoodsId());
    }

    static final class Amount {
        private final BigDecimal goodsPrice;
        private final BigDecimal couponPrice;
        private final BigDecimal freightPrice;
        private final BigDecimal orderPrice;

        private Amount(BigDecimal goodsPrice,
                       BigDecimal couponPrice,
                       BigDecimal freightPrice,
                       BigDecimal orderPrice) {
            this.goodsPrice = goodsPrice;
            this.couponPrice = couponPrice;
            this.freightPrice = freightPrice;
            this.orderPrice = orderPrice;
        }

        BigDecimal getGoodsPrice() {
            return goodsPrice;
        }

        BigDecimal getCouponPrice() {
            return couponPrice;
        }

        BigDecimal getFreightPrice() {
            return freightPrice;
        }

        BigDecimal getOrderPrice() {
            return orderPrice;
        }
    }
}
