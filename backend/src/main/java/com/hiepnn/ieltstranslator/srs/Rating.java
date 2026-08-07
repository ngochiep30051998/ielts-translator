package com.hiepnn.ieltstranslator.srs;

/** Mức độ nhớ người dùng tự chấm sau khi lật thẻ. q dùng trong công thức EF của SM-2. */
public enum Rating {
    AGAIN(0), HARD(1), GOOD(2), EASY(3);

    private final int q;

    Rating(int q) {
        this.q = q;
    }

    public int q() {
        return q;
    }
}
